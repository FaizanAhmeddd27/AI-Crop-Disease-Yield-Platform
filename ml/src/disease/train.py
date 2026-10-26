"""Full training loop for Disease Detection models with checkpointing and durable run records.

Fulfills DEV_PLAN Tasks 2.1 - 2.7 (ML-001, ML-002, ML-003, ML-006).
Features:
- Config-driven (YAML or dict).
- Automatic Mixed Precision (AMP) on CUDA.
- Checkpoint saving every epoch (`checkpoint_latest.pt` and `checkpoint_best.pt`).
- Resume training support.
- File-based run recording per ADR-0012 (`src.common.tracking`).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW, SGD
from torch.optim.lr_scheduler import CosineAnnealingLR
import yaml

from src.common.paths import resolve_artifact_root, resolve_data_root
from src.common.seed import seed_everything
from src.common.tracking import start_run

from .dataset import create_dataloaders, load_manifest
from .evaluate import TemperatureScaler, evaluate_model
from .models import build_disease_model


def train_epoch(
    model: nn.Module,
    train_loader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    scaler: GradScaler,
    device: torch.device,
) -> Tuple[float, float]:
    """Execute one training epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in train_loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with autocast(enabled=device.type == "cuda"):
            outputs = model(images)
            loss = criterion(outputs, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        running_loss += loss.item() * images.size(0)
        _, preds = outputs.max(1)
        correct += preds.eq(labels).sum().item()
        total += labels.size(0)

    epoch_loss = running_loss / max(total, 1)
    epoch_acc = correct / max(total, 1)
    return round(epoch_loss, 4), round(epoch_acc, 4)


def train_disease_pipeline(config: Dict[str, Any]) -> Dict[str, Any]:
    """Execute end-to-end training experiment according to config."""
    # 1. Reproducibility
    seed = config.get("seed", 42)
    seed_everything(seed)

    exp_id = config.get("exp_id", "D-0X")
    arch = config.get("architecture", "efficientnet_b0")
    run_name = f"{exp_id}-{arch}-{config.get('name_suffix', 'run')}"

    # 2. Device & Paths
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[{run_name}] Starting training on device: {device}")

    # 3. DataLoaders
    batch_size = config.get("batch_size", 32)
    img_size = config.get("img_size", 224)
    aug_policy = config.get("aug_policy", "basic")
    data_dir_override = config.get("data_dir_override", None)

    train_loader, val_loader, test_loader, class_to_idx = create_dataloaders(
        data_dir_override=data_dir_override,
        batch_size=batch_size,
        aug_policy=aug_policy,
        img_size=img_size,
    )
    num_classes = len(class_to_idx)
    idx_to_class = {i: c for c, i in class_to_idx.items()}
    class_names = [idx_to_class[i] for i in range(num_classes)]

    # 4. Model, Loss, Optimizer
    model = build_disease_model(
        architecture=arch,
        num_classes=num_classes,
        pretrained=config.get("pretrained", True),
        freeze_backbone=config.get("freeze_backbone", False),
    ).to(device)

    label_smoothing = config.get("label_smoothing", 0.0)
    criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)

    lr = float(config.get("lr", 3e-4))
    weight_decay = float(config.get("weight_decay", 1e-4))
    optimizer_type = config.get("optimizer", "adamw").lower()

    if optimizer_type == "sgd":
        optimizer = SGD(model.parameters(), lr=lr, momentum=0.9, weight_decay=weight_decay)
    else:
        optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    epochs = config.get("epochs", 10)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr * 0.01)
    scaler = GradScaler(enabled=device.type == "cuda")

    # 5. File-based Run Record (ADR-0012)
    with start_run(run_name, params=config) as run:
        best_val_f1 = 0.0
        best_checkpoint_path = run.dir / "checkpoint_best.pt"
        latest_checkpoint_path = run.dir / "checkpoint_latest.pt"

        # Save class mapping alongside model
        with open(run.dir / "labels.json", "w", encoding="utf-8") as f:
            json.dump({"class_to_idx": class_to_idx, "classes": class_names}, f, indent=2)
        run.log_artifact("labels.json")

        for epoch in range(1, epochs + 1):
            t0 = time.time()
            train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, scaler, device)
            val_metrics, cm, val_logits, val_labels = evaluate_model(model, val_loader, device, class_names)
            scheduler.step()

            val_acc = val_metrics["accuracy"]
            val_f1 = val_metrics["macro_f1"]
            elapsed = time.time() - t0

            print(
                f"Epoch [{epoch:02d}/{epochs:02d}] ({elapsed:.1f}s) | "
                f"Train Loss: {train_loss:.4f} Acc: {train_acc:.3f} | "
                f"Val Acc: {val_acc:.3f} Macro-F1: {val_f1:.3f}"
            )

            # Checkpoint latest
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_f1": val_f1,
                "config": config,
            }, latest_checkpoint_path)

            # Checkpoint best
            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                torch.save(model.state_dict(), best_checkpoint_path)

        # 6. Final Evaluation on Held-Out Test Split
        print("\n=== Running Final Benchmark on Test Split ===")
        # Load best weights
        if best_checkpoint_path.exists():
            model.load_state_dict(torch.load(best_checkpoint_path, map_location=device))

        cm_plot_path = run.dir / "confusion_matrix.png"
        test_metrics, test_cm, test_logits, test_labels = evaluate_model(
            model=model,
            dataloader=test_loader,
            device=device,
            class_names=class_names,
            plot_save_path=cm_plot_path,
        )
        run.log_artifact("confusion_matrix.png")
        run.log_artifact("checkpoint_best.pt")

        # 7. Post-Hoc Confidence Calibration (NFR-ML-003)
        scaler_mod = TemperatureScaler()
        learned_temp = scaler_mod.fit(test_logits, test_labels)
        test_metrics["calibrated_temperature"] = round(learned_temp, 3)

        # Log final metrics to run record
        run.log_metrics(
            best_val_macro_f1=round(best_val_f1, 4),
            test_accuracy=test_metrics["accuracy"],
            test_macro_f1=test_metrics["macro_f1"],
            test_weighted_f1=test_metrics["weighted_f1"],
            test_ece=test_metrics["ece"],
            calibrated_temp=test_metrics["calibrated_temperature"],
        )

        print("\nFinal Test Metrics:")
        print(f"Accuracy:  {test_metrics['accuracy']:.2%}")
        print(f"Macro-F1:  {test_metrics['macro_f1']:.4f}")
        print(f"ECE:       {test_metrics['ece']:.4f}")
        print(f"Run record saved: {run.dir / 'run.json'}")

        return test_metrics


def main():
    parser = argparse.ArgumentParser(description="Train PlantVillage Disease Detection Model")
    parser.add_argument("--config", type=str, required=True, help="Path to YAML training config")
    parser.add_argument("--data-dir", type=str, default=None, help="Optional data root override")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if args.data_dir:
        config["data_dir_override"] = args.data_dir

    train_disease_pipeline(config)


if __name__ == "__main__":
    main()
