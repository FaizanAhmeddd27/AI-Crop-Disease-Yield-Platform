"""Image preprocessing and data augmentation pipelines for disease classification.

Implements Task 1.5, 2.1, 2.6 (Basic vs Strong augmentations).
Ensures normalization matches ImageNet pretrained weights.
"""

from typing import Tuple
from torchvision import transforms

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def get_transforms(
    split: str = "train",
    policy: str = "basic",
    img_size: int = 224,
) -> transforms.Compose:
    """Return torchvision transform pipeline for a given split and augmentation policy.

    Args:
        split: 'train', 'val', or 'test'.
        policy: 'basic' (flips, slight rotation) or 'strong' (color jitter, affine, random erasing).
        img_size: Target image dimension (default 224 for ResNet/EfficientNet/ViT).
    """
    if split in ("val", "test", "inference"):
        return transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(img_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])

    # Training policies
    if policy == "strong":
        # Domain gap mitigation: lighting changes, cutout, and broader rotations
        return transforms.Compose([
            transforms.RandomResizedCrop(img_size, scale=(0.7, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.3),
            transforms.RandomRotation(degrees=30),
            transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.2, hue=0.1),
            transforms.RandomAffine(degrees=0, translate=(0.08, 0.08)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            transforms.RandomErasing(p=0.25, scale=(0.02, 0.2), ratio=(0.3, 3.3), value="random"),
        ])
    else:
        # Standard basic augmentation (flips, mild rotation, crop)
        return transforms.Compose([
            transforms.RandomResizedCrop(img_size, scale=(0.8, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.2),
            transforms.RandomRotation(degrees=15),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])


if __name__ == "__main__":
    t_train_basic = get_transforms("train", "basic")
    t_train_strong = get_transforms("train", "strong")
    t_val = get_transforms("val")
    print(f"Transforms successfully initialized for 224x224 (val steps: {len(t_val.transforms)})")
