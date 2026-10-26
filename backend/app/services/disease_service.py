"""Disease classification inference service (ARCH §6.1, DEV_PLAN Task 5.5).

Orchestrates the full disease prediction pipeline:
1. Image preprocessing (resize, normalize, EXIF strip)
2. TorchScript forward pass + softmax
3. Confidence threshold gating (τ = 0.60)
4. Grad-CAM overlay generation
5. Lesion severity segmentation
6. Knowledge base lookup
7. DB persistence
"""

from __future__ import annotations

import io
import logging
import time
import uuid
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import UnsupportedMediaTypeError
from app.db.models import PredictionDisease
from app.ml.gradcam import GradCAMService
from app.ml.loader import production_bundle
from app.services.knowledge_service import get_knowledge_for_class
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

# ── Image Preprocessing ───────────────────────────────────────────────

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
INPUT_SIZE = 224


def preprocess_image(image_bytes: bytes) -> tuple[torch.Tensor, np.ndarray]:
    """Convert raw upload bytes to (1,3,224,224) tensor and original RGB array.

    Mirrors the training-time validation transform exactly
    (ml/src/disease/transforms.py: Resize(256) -> CenterCrop(224) ->
    ImageNet normalization) so serving matches the eval distribution
    (DEV_PLAN Task 2.12 train/serve parity).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedMediaTypeError(
            "The uploaded file is not a readable image.",
        ) from exc
    img_rgb = np.array(img)

    # Resize(256): scale the shorter side to 256, preserving aspect ratio
    h, w = img_rgb.shape[:2]
    if h < w:
        new_h, new_w = 256, max(1, round(w * 256 / h))
    else:
        new_h, new_w = max(1, round(h * 256 / w)), 256
    resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # CenterCrop(224)
    top = max(0, (new_h - INPUT_SIZE) // 2)
    left = max(0, (new_w - INPUT_SIZE) // 2)
    cropped = np.ascontiguousarray(resized[top : top + INPUT_SIZE, left : left + INPUT_SIZE])
    if cropped.shape[0] < INPUT_SIZE or cropped.shape[1] < INPUT_SIZE:
        # Degenerate extreme-aspect fallback: pad to 224
        padded = np.zeros((INPUT_SIZE, INPUT_SIZE, 3), dtype=np.uint8)
        padded[: cropped.shape[0], : cropped.shape[1]] = cropped
        cropped = padded

    tensor = torch.from_numpy(cropped).permute(2, 0, 1).float() / 255.0

    # Normalize with ImageNet statistics
    for c in range(3):
        tensor[c] = (tensor[c] - IMAGENET_MEAN[c]) / IMAGENET_STD[c]

    return tensor.unsqueeze(0), img_rgb


# ── Severity estimation (mirrors ml/src/disease/severity.py logic) ───


def _estimate_severity(img_rgb: np.ndarray) -> dict[str, Any]:
    """Quick HSV + Lab lesion segmentation returning severity band and ratio."""
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)

    # Leaf mask
    lower_leaf = np.array([20, 30, 25])
    upper_leaf = np.array([95, 255, 255])
    leaf_mask = cv2.inRange(hsv, lower_leaf, upper_leaf)

    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_CLOSE, kernel_close)

    leaf_pixels = int(np.count_nonzero(leaf_mask))
    total_pixels = img_rgb.shape[0] * img_rgb.shape[1]

    if leaf_pixels < total_pixels * 0.05:
        return {
            "level": "unknown",
            "ratio": 0.0,
            "method": "lesion_area_ratio",
            "note": "Insufficient leaf surface",
        }

    h, s, v = cv2.split(hsv)
    _, a_chan, _ = cv2.split(lab)

    necrotic = ((v < 85) | ((h < 18) & (s > 60))) & (leaf_mask > 0)
    chlorotic = ((h >= 15) & (h <= 34) & (s > 90) & (v > 90)) & (leaf_mask > 0)
    lab_lesion = (a_chan > 138) & (leaf_mask > 0)

    raw_lesions = (necrotic | chlorotic | lab_lesion).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    filtered = cv2.morphologyEx(raw_lesions, cv2.MORPH_OPEN, kernel)

    lesion_pixels = int(np.count_nonzero(filtered))
    ratio_pct = min(100.0, (lesion_pixels / max(1, leaf_pixels)) * 100.0)

    if ratio_pct < 10.0:
        level = "low"
    elif ratio_pct < 30.0:
        level = "moderate"
    else:
        level = "severe"

    return {
        "level": level,
        "ratio": round(ratio_pct, 2),
        "method": "lesion_area_ratio",
        "note": "Estimated via dual HSV+Lab thresholding",
    }


# ── Main prediction pipeline ──────────────────────────────────────────


def classify_with_temperature(logits: torch.Tensor, temperature: float) -> torch.Tensor:
    """Apply the exported calibration temperature (NFR-ML-003) then softmax."""
    return F.softmax(logits / max(1e-6, float(temperature)), dim=1)


async def predict_disease(
    image_bytes: bytes,
    db: Session,
    user_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run the full disease classification and explanation pipeline.

    Returns a dict matching ``DiseasePredictResponse`` schema.
    """
    settings = settings or get_settings()
    t0 = time.perf_counter()
    prediction_id = uuid.uuid4().hex

    bundle = production_bundle
    if not bundle.disease_ready or bundle.disease_model is None:
        raise RuntimeError("Disease model is not loaded. Check model artifacts.")

    # 1. Preprocess
    input_tensor, original_rgb = preprocess_image(image_bytes)

    # 2. Inference (+ exported calibration temperature, NFR-ML-003)
    with torch.no_grad():
        logits = bundle.disease_model(input_tensor)
    temperature = float(bundle.disease_config.get("temperature", 1.0) or 1.0)
    probs = classify_with_temperature(logits, temperature)[0]

    # 3. Top-K predictions
    top_k_vals, top_k_idx = torch.topk(probs, k=min(5, probs.shape[0]))
    top_class_idx = int(top_k_idx[0].item())
    top_confidence = float(top_k_vals[0].item())

    # Resolve class label
    class_id = bundle.disease_labels.get(str(top_class_idx), f"class_{top_class_idx}")

    # Parse crop and disease from class_id (format: "Crop___Disease")
    parts = class_id.split("___")
    crop_name = parts[0].replace("_", " ") if parts else "Unknown"
    disease_name = parts[1].replace("_", " ") if len(parts) > 1 else "Unknown"
    is_healthy = "healthy" in class_id.lower()

    # 4. Status determination
    status = "uncertain" if top_confidence < settings.confidence_threshold else "ok"

    # 5. Top-K list
    top_k_list = []
    for v, idx in zip(top_k_vals, top_k_idx, strict=True):
        cid = bundle.disease_labels.get(str(int(idx.item())), f"class_{idx.item()}")
        top_k_list.append({"class_id": cid, "confidence": round(float(v.item()), 4)})

    # 6. Grad-CAM explanation
    overlay_url = ""
    original_url = ""
    quality_warnings: list[str] = []
    leaf_focus: float | None = None
    storage = StorageService(settings)

    try:
        gradcam = GradCAMService(bundle.disease_model)
        # Need grad-enabled tensor for Grad-CAM
        grad_tensor = input_tensor.clone().detach().requires_grad_(False)
        heatmap = gradcam.generate_heatmap(grad_tensor, target_class=top_class_idx)
        overlay_bytes = gradcam.generate_overlay(original_rgb, heatmap)

        # Saliency sanity check (AC-9): warn when activation mass sits mostly
        # off-leaf (e.g., fingers or bright soil in frame). Fractions are computed
        # against the central 70% mask when no explicit leaf mask is available.
        leaf_focus = gradcam.leaf_focus_fraction(heatmap)
        quality_warnings = []
        if leaf_focus < 0.50:
            quality_warnings.append(
                "low_saliency_quality: most activation fell outside the leaf area — "
                "retake the photo filling the frame with a single leaf, without fingers or soil."
            )

        overlay_path = f"overlays/{prediction_id}.png"
        overlay_url = await storage.upload_file(
            overlay_bytes,
            overlay_path,
            bucket_name="agri-overlays",
            content_type="image/png",
        )
    except Exception as e:
        logger.warning(f"Grad-CAM generation failed: {e}")
        overlay_url = ""

    try:
        clean_jpeg, _, _ = storage.strip_exif_and_prepare_jpeg(image_bytes)
        original_path = f"originals/{prediction_id}.jpg"
        original_url = await storage.upload_file(
            clean_jpeg, original_path, bucket_name="agri-uploads"
        )
    except Exception as e:
        logger.warning(f"Original image upload failed: {e}")
        original_url = ""

    # 7. Severity
    severity = _estimate_severity(original_rgb)

    # 8. Knowledge base recommendations
    kb = get_knowledge_for_class(class_id, db)
    if kb:
        recommendations = {
            "summary": kb.get("summary", ""),
            "actions": kb.get("actions", []),
            "prevention": kb.get("prevention", []),
            "sources": kb.get("sources", []),
            "disclaimer": (
                kb.get("disclaimer", "Decision support only. Consult a local agronomist.")
            ),
        }
    else:
        summary_text = (
            f"{disease_name} detected on {crop_name}."
            if not is_healthy
            else f"{crop_name} appears healthy."
        )
        recommendations = {
            "summary": summary_text,
            "actions": [],
            "prevention": [],
            "sources": [],
            "disclaimer": "Decision support only. Consult a local agronomist.",
        }

    # 9. Persist to DB
    try:
        record = PredictionDisease(
            id=prediction_id,
            user_id=user_id,
            image_url=original_url,
            overlay_url=overlay_url,
            crop=crop_name,
            disease_class=class_id,
            confidence=top_confidence,
            is_healthy=is_healthy,
            severity_band=severity["level"],
            severity_ratio_pct=severity["ratio"],
        )
        db.add(record)
        db.commit()
    except Exception as e:
        logger.warning(f"DB persistence failed: {e}")
        db.rollback()

    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "prediction_id": prediction_id,
        "status": status,
        "prediction": {
            "class_id": class_id,
            "crop": crop_name,
            "disease": disease_name,
            "is_healthy": is_healthy,
            "confidence": round(top_confidence, 4),
            "top_k": top_k_list,
        },
        "severity": severity,
        "explanation": {
            "method": "grad-cam",
            "overlay_url": overlay_url,
            "original_url": original_url,
            "quality_warnings": quality_warnings,
            "leaf_focus_fraction": round(leaf_focus, 4) if leaf_focus is not None else None,
        },
        "recommendations": recommendations,
        "model": {
            "name": bundle.disease_card.get("model_name", "EfficientNet-B0"),
            "version": bundle.disease_card.get("version", "v0.1.0"),
        },
        "latency_ms": latency_ms,
    }
