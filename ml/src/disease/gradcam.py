"""Grad-CAM (Gradient-weighted Class Activation Mapping) for Disease Visual Explanations.

Fulfills DEV_PLAN Tasks 4.1, 4.2, 4.3 (FR-X-001, FR-X-002, FR-X-010).
Extracts fine-grained spatial saliency heatmaps highlighting leaf lesions that
drove the model's diagnostic classification.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F


def get_default_target_layer(model: nn.Module) -> nn.Module:
    """Resolve default target convolutional layer for Grad-CAM across architectures."""
    # EfficientNet-B0
    if hasattr(model, "features"):
        return model.features[-1]
    # ResNet-50
    if hasattr(model, "layer4"):
        return model.layer4[-1]
    # Fallback to last Conv2d in module list
    conv_layers = [m for m in model.modules() if isinstance(m, nn.Conv2d)]
    if conv_layers:
        return conv_layers[-1]
    raise ValueError("Could not automatically locate a convolutional layer for Grad-CAM.")


class GradCAM:
    """Gradient-weighted Class Activation Mapping generator (supports eager and TorchScript)."""

    def __init__(self, model: Union[nn.Module, torch.jit.ScriptModule], target_layer: Optional[nn.Module] = None):
        self.model = model
        self.model.eval()
        self.is_script = isinstance(model, (torch.jit.ScriptModule, torch.jit._script.RecursiveScriptModule))
        self.activations: Optional[torch.Tensor] = None
        self.gradients: Optional[torch.Tensor] = None

        if not self.is_script:
            self.target_layer = target_layer or get_default_target_layer(self.model)
            self._register_hooks()

    def _register_hooks(self) -> None:
        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0].detach()

        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_full_backward_hook(backward_hook)

    def generate_heatmap(
        self,
        input_tensor: torch.Tensor,
        target_class: Optional[int] = None,
    ) -> np.ndarray:
        """Compute normalized Grad-CAM heatmap array in range [0.0, 1.0]."""
        self.model.zero_grad()

        if self.is_script:
            feats = self.model.features(input_tensor)
            feats.retain_grad()
            pooled = self.model.avgpool(feats)
            flat = torch.flatten(pooled, 1)
            logits = self.model.classifier(flat)
            if target_class is None:
                target_class = int(logits.argmax(dim=1).item())
            score = logits[0, target_class]
            score.backward()

            weights = torch.mean(feats.grad, dim=(2, 3), keepdim=True)
            cam = torch.sum(weights * feats, dim=1, keepdim=True)
            cam = F.relu(cam)
        else:
            logits = self.model(input_tensor)
            if target_class is None:
                target_class = int(logits.argmax(dim=1).item())

            score = logits[0, target_class]
            score.backward()

            if self.gradients is None or self.activations is None:
                raise RuntimeError("Gradients or activations were not captured. Check target_layer registration.")

            # Global average pool gradients over spatial dimensions (H, W) -> weights alpha_k
            weights = torch.mean(self.gradients, dim=(2, 3), keepdim=True)  # [1, C, 1, 1]

            # Weighted combination of forward activation maps
            cam = torch.sum(weights * self.activations, dim=1, keepdim=True)  # [1, 1, H, W]

            # ReLU: retain only features having positive influence on the target score
            cam = F.relu(cam)

        # Interpolate heatmap to match input spatial dimensions
        h, w = input_tensor.shape[2], input_tensor.shape[3]
        cam = F.interpolate(cam, size=(h, w), mode="bilinear", align_corners=False)

        # Normalize to [0.0, 1.0]
        cam_np = cam.squeeze().detach().cpu().numpy()
        cam_min, cam_max = cam_np.min(), cam_np.max()
        if cam_max - cam_min > 1e-8:
            cam_np = (cam_np - cam_min) / (cam_max - cam_min)
        else:
            cam_np = np.zeros_like(cam_np)

        return cam_np.astype(np.float32)

    def generate_overlay(
        self,
        original_image_rgb: np.ndarray,
        heatmap: np.ndarray,
        alpha: float = 0.45,
        colormap: int = cv2.COLORMAP_JET,
    ) -> np.ndarray:
        """Blend colorized heatmap overlay with the original RGB leaf photo."""
        orig_h, orig_w = original_image_rgb.shape[:2]

        # Resize heatmap to match original image dimensions
        resized_heatmap = cv2.resize(heatmap, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        heatmap_uint8 = np.uint8(255 * resized_heatmap)

        # Apply colormap
        colored_heatmap = cv2.applyColorMap(heatmap_uint8, colormap)
        colored_heatmap_rgb = cv2.cvtColor(colored_heatmap, cv2.COLOR_BGR2RGB)

        # Alpha blend: (1 - alpha) * original + alpha * heatmap
        blended = np.clip(
            (1.0 - alpha) * original_image_rgb.astype(np.float32) + alpha * colored_heatmap_rgb.astype(np.float32),
            0,
            255,
        ).astype(np.uint8)

        return blended

    def overlay_to_png_bytes(self, overlay_rgb: np.ndarray) -> bytes:
        """Encode RGB overlay array as PNG image bytes."""
        overlay_bgr = cv2.cvtColor(overlay_rgb, cv2.COLOR_RGB2BGR)
        success, buffer = cv2.imencode(".png", overlay_bgr)
        if not success:
            raise RuntimeError("Failed to encode Grad-CAM overlay to PNG.")
        return buffer.tobytes()

    def sanity_check_leaf_focus(
        self,
        heatmap: np.ndarray,
        leaf_mask: Optional[np.ndarray] = None,
        leaf_focus_threshold: float = 0.50,
    ) -> Tuple[bool, float]:
        """Verify that heatmap activation mass falls predominantly on the leaf rather than background.

        Returns:
            (passed_sanity, fraction_of_activation_on_leaf)
        """
        if leaf_mask is None:
            # Assume center 70% bounding region is leaf
            h, w = heatmap.shape
            leaf_mask = np.zeros((h, w), dtype=bool)
            pad_h, pad_w = int(h * 0.15), int(w * 0.15)
            leaf_mask[pad_h : h - pad_h, pad_w : w - pad_w] = True

        total_activation = float(np.sum(heatmap))
        if total_activation < 1e-6:
            return True, 1.0

        leaf_activation = float(np.sum(heatmap[leaf_mask]))
        fraction_on_leaf = leaf_activation / total_activation

        is_focused = fraction_on_leaf >= leaf_focus_threshold
        return is_focused, round(fraction_on_leaf, 4)


if __name__ == "__main__":
    import sys
    ml_root = str(Path(__file__).resolve().parents[2])
    if ml_root not in sys.path:
        sys.path.insert(0, ml_root)
    from src.disease.models import build_disease_model

    print("Testing Grad-CAM explanation module...")
    dummy_model = build_disease_model("efficientnet_b0", num_classes=38, pretrained=False)
    gradcam = GradCAM(dummy_model)

    dummy_tensor = torch.randn(1, 3, 224, 224, requires_grad=True)
    heatmap = gradcam.generate_heatmap(dummy_tensor, target_class=5)

    print("Heatmap shape:", heatmap.shape, "Range:", f"[{heatmap.min():.2f}, {heatmap.max():.2f}]")
    assert heatmap.shape == (224, 224)
    assert 0.0 <= heatmap.min() <= heatmap.max() <= 1.0

    dummy_rgb = np.full((224, 224, 3), 120, dtype=np.uint8)
    overlay = gradcam.generate_overlay(dummy_rgb, heatmap)
    assert overlay.shape == (224, 224, 3)

    png_bytes = gradcam.overlay_to_png_bytes(overlay)
    assert len(png_bytes) > 0

    passed, frac = gradcam.sanity_check_leaf_focus(heatmap)
    print(f"Sanity Check Passed: {passed} (Leaf Focus: {frac * 100:.1f}%)")
    print("Grad-CAM module verified.")
