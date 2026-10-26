"""Grad-CAM for inference service (ARCH §6.1, Task 4.1)."""

from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class GradCAMService:
    """Computes Grad-CAM saliency heatmaps on PyTorch vision models (eager & TorchScript)."""

    def __init__(self, model: nn.Module | torch.jit.ScriptModule):
        self.model = model
        self.model.eval()
        script_types = (torch.jit.ScriptModule, torch.jit._script.RecursiveScriptModule)
        self.is_script = isinstance(model, script_types)
        self.activations: torch.Tensor | None = None
        self.gradients: torch.Tensor | None = None

        if not self.is_script:
            self._target_layer = self._find_target_layer()
            self._register_hooks()

    def _find_target_layer(self) -> nn.Module:
        model = self.model
        if hasattr(model, "features") and isinstance(model.features, nn.Module):
            return model.features[-1]  # type: ignore[index]
        convs = [m for m in model.modules() if isinstance(m, nn.Conv2d)]
        if convs:
            return convs[-1]
        raise ValueError("No Conv2d layer found for Grad-CAM.")

    def _register_hooks(self) -> None:
        def forward_hook(_module: nn.Module, _inp: object, out: torch.Tensor) -> None:
            self.activations = out.detach()

        def backward_hook(_module: nn.Module, _grad_in: object, grad_out: tuple) -> None:
            self.gradients = grad_out[0].detach()

        self._target_layer.register_forward_hook(forward_hook)
        self._target_layer.register_full_backward_hook(backward_hook)

    def generate_heatmap(self, input_tensor: torch.Tensor, target_class: int) -> np.ndarray:
        self.model.zero_grad()
        if self.is_script:
            feats: torch.Tensor = self.model.features(input_tensor)  # type: ignore[operator]
            feats.retain_grad()
            pooled: torch.Tensor = self.model.avgpool(feats)  # type: ignore[operator]
            flat = torch.flatten(pooled, 1)
            logits: torch.Tensor = self.model.classifier(flat)  # type: ignore[operator]
            score = logits[0, target_class]
            score.backward()

            assert feats.grad is not None
            weights = torch.mean(feats.grad, dim=(2, 3), keepdim=True)
            cam = torch.sum(weights * feats, dim=1, keepdim=True)
            cam = F.relu(cam)
        else:
            logits = self.model(input_tensor)
            score = logits[0, target_class]
            score.backward()

            if self.gradients is None or self.activations is None:
                return np.zeros((input_tensor.shape[2], input_tensor.shape[3]), dtype=np.float32)

            weights = torch.mean(self.gradients, dim=(2, 3), keepdim=True)
            cam = torch.sum(weights * self.activations, dim=1, keepdim=True)
            cam = F.relu(cam)

        h, w = input_tensor.shape[2], input_tensor.shape[3]
        cam = F.interpolate(cam, size=(h, w), mode="bilinear", align_corners=False)
        cam_np = cam.squeeze().detach().cpu().numpy()

        cam_min, cam_max = cam_np.min(), cam_np.max()
        if cam_max - cam_min > 1e-8:
            cam_np = (cam_np - cam_min) / (cam_max - cam_min)
        else:
            cam_np = np.zeros_like(cam_np)
        return cam_np.astype(np.float32)

    def generate_overlay(
        self, orig_rgb: np.ndarray, heatmap: np.ndarray, alpha: float = 0.45
    ) -> bytes:
        orig_h, orig_w = orig_rgb.shape[:2]
        resized = cv2.resize(heatmap, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        heat_u8 = (255.0 * resized).astype(np.uint8)

        colored = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)

        blend = (1.0 - alpha) * orig_rgb.astype(np.float32)
        blend += alpha * colored_rgb.astype(np.float32)
        blended = np.clip(blend, 0, 255).astype(np.uint8)
        blended_bgr = cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)

        success, buf = cv2.imencode(".png", blended_bgr)
        if not success:
            raise RuntimeError("Failed to encode Grad-CAM overlay")
        return buf.tobytes()

    def leaf_focus_fraction(
        self, heatmap: np.ndarray, leaf_mask: np.ndarray | None = None
    ) -> float:
        """Fraction of saliency mass inside the leaf region (saliency sanity, AC-9).

        Falls back to a central 70% bounding mask when no explicit leaf mask
        is supplied (mirrors ``ml/src/disease/gradcam.py``).
        """
        if leaf_mask is None:
            h, w = heatmap.shape
            leaf_mask = np.zeros((h, w), dtype=bool)
            pad_h, pad_w = int(h * 0.15), int(w * 0.15)
            leaf_mask[pad_h : h - pad_h, pad_w : w - pad_w] = True

        total = float(np.sum(heatmap))
        if total < 1e-6:
            return 1.0
        return float(np.sum(heatmap[leaf_mask]) / total)
