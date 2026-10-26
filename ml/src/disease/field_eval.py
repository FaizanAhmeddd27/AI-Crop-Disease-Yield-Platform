"""Field evaluation and domain-gap analysis using the PlantDoc dataset.

Fulfills DEV_PLAN Tasks 2.8 and 2.10 (NFR-ML-002, NFR-ML-007).
Evaluates models trained on lab-style PlantVillage images against real-world
field imagery (variable illumination, natural backgrounds, occlusions).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset

from .evaluate import calculate_ece, plot_confusion_matrix
from .transforms import get_transforms

# Standard PlantDoc to PlantVillage class mapping dictionary
PLANTDOC_TO_PLANTVILLAGE: Dict[str, str] = {
    "Apple Scab Leaf": "Apple___Apple_scab",
    "Apple leaf": "Apple___healthy",
    "Apple rust leaf": "Apple___Cedar_apple_rust",
    "Bell_pepper leaf spot": "Pepper,_bell___Bacterial_spot",
    "Bell_pepper leaf": "Pepper,_bell___healthy",
    "Blueberry leaf": "Blueberry___healthy",
    "Cherry leaf": "Cherry_(including_sour)___healthy",
    "Corn Gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn leaf blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Corn rust leaf": "Corn_(maize)___Common_rust_",
    "grape leaf black rot": "Grape___Black_rot",
    "grape leaf": "Grape___healthy",
    "Peach leaf": "Peach___healthy",
    "Potato Early blight leaf": "Potato___Early_blight",
    "Potato leaf late blight": "Potato___Late_blight",
    "Potato leaf": "Potato___healthy",
    "Raspberry leaf": "Raspberry___healthy",
    "Soyabean leaf": "Soybean___healthy",
    "Squash Powdery mildew leaf": "Squash___Powdery_mildew",
    "Strawberry leaf": "Strawberry___healthy",
    "Tomato Early blight leaf": "Tomato___Early_blight",
    "Tomato Septoria leaf spot": "Tomato___Septoria_leaf_spot",
    "Tomato leaf bacterial spot": "Tomato___Bacterial_spot",
    "Tomato leaf late blight": "Tomato___Late_blight",
    "Tomato leaf mosaic virus": "Tomato___Tomato_mosaic_virus",
    "Tomato leaf yellow virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato leaf": "Tomato___healthy",
    "Tomato mold leaf": "Tomato___Leaf_Mold",
    "Tomato two spotted spider mites leaf": "Tomato___Spider_mites Two-spotted_spider_mite",
}


class FieldDataset(Dataset):
    """Dataset loading real-world field images mapped to PlantVillage classes."""

    def __init__(
        self,
        samples: List[Tuple[Path, str]],
        class_to_idx: Dict[str, int],
        transform: Optional[Any] = None,
    ):
        self.samples = samples
        self.class_to_idx = class_to_idx
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        img_path, pv_class = self.samples[idx]
        with Image.open(img_path) as img:
            image = img.convert("RGB")

        if self.transform:
            image = self.transform(image)

        label = self.class_to_idx[pv_class]
        return image, label


def evaluate_field_domain_gap(
    model: nn.Module,
    field_data_dir: Path | str,
    class_to_idx: Dict[str, int],
    device: torch.device,
    save_plot_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Scan PlantDoc field directory, evaluate model, and calculate the domain gap."""
    field_dir = Path(field_data_dir)
    if not field_dir.exists():
        return {
            "status": "dataset_not_found",
            "message": f"Field dataset not found at {field_dir}. Skipping field evaluation.",
        }

    # Discover and map field images
    valid_samples: List[Tuple[Path, str]] = []
    for subfolder in field_dir.iterdir():
        if subfolder.is_dir() and subfolder.name in PLANTDOC_TO_PLANTVILLAGE:
            pv_target = PLANTDOC_TO_PLANTVILLAGE[subfolder.name]
            if pv_target in class_to_idx:
                for img_p in subfolder.glob("*.*"):
                    if img_p.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                        valid_samples.append((img_p, pv_target))

    if not valid_samples:
        return {"status": "no_mapped_samples_found", "sample_count": 0}

    print(f"Mapped {len(valid_samples)} real-world field images across {len(set(s[1] for s in valid_samples))} classes.")

    val_transform = get_transforms("val", img_size=224)
    field_dataset = FieldDataset(valid_samples, class_to_idx, transform=val_transform)
    field_loader = DataLoader(field_dataset, batch_size=32, shuffle=False, num_workers=2)

    model.eval()
    all_preds = []
    all_labels = []
    all_probs = []

    with torch.no_grad():
        for images, labels in field_loader:
            images = images.to(device)
            logits = model(images)
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            preds = np.argmax(probs, axis=1)

            all_probs.append(probs)
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    probs_np = np.concatenate(all_probs, axis=0)
    preds_np = np.array(all_preds)
    labels_np = np.array(all_labels)

    field_acc = float((preds_np == labels_np).mean())
    field_f1 = float(f1_score(labels_np, preds_np, average="macro", zero_division=0))
    field_ece = calculate_ece(probs_np, labels_np)

    # Error analysis: Hardest classes in the field
    unique_classes_evaluated = sorted(list(set(labels_np)))
    per_class_scores = f1_score(labels_np, preds_np, average=None, zero_division=0, labels=unique_classes_evaluated)
    idx_to_class = {i: c for c, i in class_to_idx.items()}

    hardest_classes = sorted(
        [{"class": idx_to_class[idx], "f1": round(float(score), 4)} for idx, score in zip(unique_classes_evaluated, per_class_scores)],
        key=lambda x: x["f1"]
    )[:5]

    report = {
        "status": "completed",
        "sample_count": len(valid_samples),
        "field_accuracy": round(field_acc, 4),
        "field_macro_f1": round(field_f1, 4),
        "field_ece": field_ece,
        "hardest_field_classes": hardest_classes,
    }

    if save_plot_path:
        cm = confusion_matrix(labels_np, preds_np, labels=unique_classes_evaluated)
        eval_names = [idx_to_class[i] for i in unique_classes_evaluated]
        plot_confusion_matrix(cm, eval_names, save_path=save_plot_path)

    return report


if __name__ == "__main__":
    print(f"PlantDoc mapping defined: {len(PLANTDOC_TO_PLANTVILLAGE)} real-world disease/crop categories.")
