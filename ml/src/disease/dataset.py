"""PyTorch Dataset and DataLoader generators for PlantVillage disease classification.

Fulfills DEV_PLAN Task 2.1.
Loads splits generated in Phase 1 (`train_split.csv`, `val_split.csv`, `test_split.csv`).
Handles dynamic path resolution across both Kaggle and local development.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

try:
    from src.common.paths import resolve_data_root
except ImportError:
    def resolve_data_root() -> Path:
        return Path(__file__).resolve().parents[2] / "data"

from .transforms import get_transforms


class PlantVillageDataset(Dataset):
    """PyTorch Dataset loading PlantVillage images from split index CSVs."""

    def __init__(
        self,
        split_csv: Path | str,
        class_to_idx: Dict[str, int],
        transform: Optional[Callable] = None,
        data_dir_override: Optional[Path | str] = None,
    ):
        self.df = pd.read_csv(split_csv)
        self.class_to_idx = class_to_idx
        self.transform = transform
        self.data_dir_override = Path(data_dir_override) if data_dir_override else None

        # Verify class_ids are in class_to_idx
        for cid in self.df["class_id"].unique():
            if cid not in self.class_to_idx:
                raise ValueError(f"Unknown class_id in CSV: '{cid}'")

    def __len__(self) -> int:
        return len(self.df)

    def _resolve_image_path(self, row: pd.Series) -> Path:
        """Resolve actual image path on disk across Kaggle and local environments."""
        # 1. Try override directory + relative path
        if self.data_dir_override:
            override_path = self.data_dir_override / row["relative_path"]
            if override_path.exists():
                return override_path

        # 2. Try the file_path stored during Phase 1
        recorded_path = Path(row["file_path"])
        if recorded_path.exists():
            return recorded_path

        # 3. Try resolving from local data/raw directory
        local_raw = resolve_data_root() / "raw" / "plantvillage" / row["relative_path"]
        if local_raw.exists():
            return local_raw

        # 4. Check Kaggle input fallbacks
        kaggle_fallback = Path("/kaggle/input/plantvillage-dataset/color") / row["relative_path"]
        if kaggle_fallback.exists():
            return kaggle_fallback

        raise FileNotFoundError(
            f"Image not found at {recorded_path} or relative path {row['relative_path']}. "
            f"Provide data_dir_override when creating Dataset."
        )

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        row = self.df.iloc[idx]
        img_path = self._resolve_image_path(row)

        with Image.open(img_path) as img:
            image = img.convert("RGB")

        if self.transform:
            image = self.transform(image)

        label = self.class_to_idx[row["class_id"]]
        return image, label


def load_manifest(manifest_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load data_manifest.json with class-to-index mapping."""
    if manifest_path is None:
        manifest_path = resolve_data_root() / "manifests" / "data_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_dataloaders(
    processed_dir: Optional[Path | str] = None,
    manifest_path: Optional[Path | str] = None,
    data_dir_override: Optional[Path | str] = None,
    batch_size: int = 32,
    num_workers: int = 2,
    aug_policy: str = "basic",
    img_size: int = 224,
) -> Tuple[DataLoader, DataLoader, DataLoader, Dict[str, int]]:
    """Factory creating Train, Validation, and Test PyTorch DataLoaders.

    Returns:
        (train_loader, val_loader, test_loader, class_to_idx)
    """
    if processed_dir is None:
        processed_dir = resolve_data_root() / "processed"
    processed_dir = Path(processed_dir)

    manifest = load_manifest(manifest_path)
    class_to_idx = manifest["class_to_idx"]

    # Initialize transforms
    train_transform = get_transforms(split="train", policy=aug_policy, img_size=img_size)
    val_transform = get_transforms(split="val", img_size=img_size)

    # Initialize datasets
    train_dataset = PlantVillageDataset(
        split_csv=processed_dir / "train_split.csv",
        class_to_idx=class_to_idx,
        transform=train_transform,
        data_dir_override=data_dir_override,
    )
    val_dataset = PlantVillageDataset(
        split_csv=processed_dir / "val_split.csv",
        class_to_idx=class_to_idx,
        transform=val_transform,
        data_dir_override=data_dir_override,
    )
    test_dataset = PlantVillageDataset(
        split_csv=processed_dir / "test_split.csv",
        class_to_idx=class_to_idx,
        transform=val_transform,
        data_dir_override=data_dir_override,
    )

    pin_memory = torch.cuda.is_available()

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    return train_loader, val_loader, test_loader, class_to_idx


if __name__ == "__main__":
    manifest = load_manifest()
    print(f"Loaded manifest with {manifest['counts']['num_classes']} classes.")
    print("Class mapping sample:", list(manifest["class_to_idx"].items())[:5])
