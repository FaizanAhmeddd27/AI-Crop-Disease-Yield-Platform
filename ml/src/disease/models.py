"""Model definitions and factory for Disease Classification experiments (D-01 to D-06).

Architectures:
- D-01: BaselineCNN (4 conv blocks, trained from scratch).
- D-02: ResNet-50 (ImageNet pretrained, head replacement, stage freezing).
- D-03, D-05, D-06: EfficientNet-B0 (ImageNet pretrained, compact candidate for CPU serving).
- D-04: Vision Transformer (ViT-B/16, ImageNet pretrained).
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torchvision.models import (
    EfficientNet_B0_Weights,
    ResNet50_Weights,
    ViT_B_16_Weights,
    efficientnet_b0,
    resnet50,
    vit_b_16,
)


class BaselineCNN(nn.Module):
    """Small 4-stage CNN trained from scratch (Exp D-01 reference floor)."""

    def __init__(self, num_classes: int = 38, in_channels: int = 3):
        super().__init__()
        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            # Block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            # Block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            # Block 4
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.2),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.pool(x)
        x = torch.flatten(x, 1)
        x = self.classifier(x)
        return x


def build_disease_model(
    architecture: str,
    num_classes: int = 38,
    pretrained: bool = True,
    freeze_backbone: bool = False,
) -> nn.Module:
    """Model factory returning the configured PyTorch neural network.

    Args:
        architecture: 'baseline_cnn', 'resnet50', 'efficientnet_b0', or 'vit_b16'.
        num_classes: Number of disease categories (38 for PlantVillage).
        pretrained: Whether to initialize with ImageNet weights.
        freeze_backbone: If True, freezes feature extractor parameters for linear probe training.
    """
    arch = architecture.lower().strip()

    if arch in ("baseline_cnn", "baseline", "cnn"):
        return BaselineCNN(num_classes=num_classes)

    elif arch in ("resnet50", "resnet_50", "resnet"):
        weights = ResNet50_Weights.DEFAULT if pretrained else None
        model = resnet50(weights=weights)

        if freeze_backbone:
            for param in model.parameters():
                param.requires_grad = False

        in_features = model.fc.in_features
        model.fc = nn.Linear(in_features, num_classes)
        return model

    elif arch in ("efficientnet_b0", "efficientnet", "effnet_b0"):
        weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
        model = efficientnet_b0(weights=weights)

        if freeze_backbone:
            for param in model.features.parameters():
                param.requires_grad = False

        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
        return model

    elif arch in ("vit_b16", "vit", "vision_transformer"):
        # Try torchvision ViT first
        weights = ViT_B_16_Weights.DEFAULT if pretrained else None
        model = vit_b_16(weights=weights)

        if freeze_backbone:
            for param in model.encoder.parameters():
                param.requires_grad = False

        in_features = model.heads.head.in_features
        model.heads.head = nn.Linear(in_features, num_classes)
        return model

    else:
        raise ValueError(
            f"Unsupported architecture: '{architecture}'. "
            f"Supported: 'baseline_cnn', 'resnet50', 'efficientnet_b0', 'vit_b16'"
        )


def get_target_layer_for_gradcam(model: nn.Module, architecture: str) -> nn.Module:
    """Return the designated target convolutional/attention layer for Grad-CAM."""
    arch = architecture.lower()
    if "resnet" in arch:
        return model.layer4[-1]
    elif "efficientnet" in arch or "effnet" in arch:
        return model.features[-1]
    elif "vit" in arch:
        return model.encoder.layers[-1].ln_1
    elif isinstance(model, BaselineCNN):
        return model.features[-2]  # Last conv block before maxpool
    else:
        raise ValueError(f"Grad-CAM target layer unknown for architecture: {architecture}")


if __name__ == "__main__":
    print("Testing model architectures with dummy input (2, 3, 224, 224)...")
    dummy = torch.randn(2, 3, 224, 224)

    for arch in ["baseline_cnn", "resnet50", "efficientnet_b0"]:
        net = build_disease_model(arch, num_classes=38, pretrained=False)
        out = net(dummy)
        print(f"[{arch}] output shape: {tuple(out.shape)}")
        assert out.shape == (2, 38), f"Expected (2, 38), got {out.shape}"

    print("All model forward passes verified.")
