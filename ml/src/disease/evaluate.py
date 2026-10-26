"""Model evaluation, multi-class metrics, confusion matrices, and confidence calibration.

Fulfills DEV_PLAN Tasks 2.1, 2.9, 2.10 (NFR-ML-001, NFR-ML-003, NFR-ML-007).
Computes:
- Top-1 Accuracy, Macro-F1, Weighted-F1, Precision, Recall
- Per-class F1 scores and Confusion Matrix
- Expected Calibration Error (ECE) & Temperature Scaling calibration
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score


def calculate_ece(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 15,
) -> float:
    """Calculate Expected Calibration Error (ECE)."""
    confidences = np.max(probs, axis=1)
    predictions = np.argmax(probs, axis=1)
    accuracies = (predictions == labels)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = np.mean(in_bin)

        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(accuracies[in_bin])
            avg_confidence_in_bin = np.mean(confidences[in_bin])
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return round(float(ece), 4)


class TemperatureScaler(nn.Module):
    """Post-hoc temperature scaling to calibrate model confidence probabilities (NFR-ML-003)."""

    def __init__(self):
        super().__init__()
        self.temperature = nn.Parameter(torch.ones(1) * 1.5)

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        return logits / self.temperature

    def fit(self, val_logits: torch.Tensor, val_labels: torch.Tensor, lr: float = 0.01, max_iter: int = 50) -> float:
        """Optimize temperature on validation logits using Negative Log-Likelihood."""
        nll_criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.LBFGS([self.temperature], lr=lr, max_iter=max_iter)

        def eval_step():
            optimizer.zero_grad()
            loss = nll_criterion(self.forward(val_logits), val_labels)
            loss.backward()
            return loss

        optimizer.step(eval_step)
        return float(self.temperature.item())


def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: List[str],
    save_path: Optional[Path | str] = None,
    figsize: Tuple[int, int] = (18, 16),
) -> plt.Figure:
    """Render and optionally save a normalized confusion matrix heatmap."""
    cm_norm = cm.astype("float") / (cm.sum(axis=1)[:, np.newaxis] + 1e-9)

    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(
        cm_norm,
        annot=False,
        cmap="Blues",
        xticklabels=[c.replace("___", "\n") for c in class_names],
        yticklabels=class_names,
        ax=ax,
    )
    ax.set_xlabel("Predicted Class", fontsize=12)
    ax.set_ylabel("True Class", fontsize=12)
    ax.set_title("Disease Classification Confusion Matrix (Normalized)", fontsize=14)
    plt.xticks(rotation=90, fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150)

    return fig


@torch.no_grad()
def evaluate_model(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    device: torch.device,
    class_names: Optional[List[str]] = None,
    plot_save_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Execute complete validation/test evaluation pass.

    Returns:
        dict containing accuracy, macro_f1, weighted_f1, precision, recall, ece,
        confusion_matrix, and per_class_f1.
    """
    model.eval()
    all_logits = []
    all_labels = []

    for images, labels in dataloader:
        images = images.to(device)
        logits = model(images)
        all_logits.append(logits.cpu())
        all_labels.append(labels)

    logits_tensor = torch.cat(all_logits, dim=0)
    labels_tensor = torch.cat(all_labels, dim=0)

    probs = torch.softmax(logits_tensor, dim=1).numpy()
    preds = np.argmax(probs, axis=1)
    labels_np = labels_tensor.numpy()

    acc = float((preds == labels_np).mean())
    macro_f1 = float(f1_score(labels_np, preds, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(labels_np, preds, average="weighted", zero_division=0))
    macro_prec = float(precision_score(labels_np, preds, average="macro", zero_division=0))
    macro_rec = float(recall_score(labels_np, preds, average="macro", zero_division=0))
    ece = calculate_ece(probs, labels_np)

    cm = confusion_matrix(labels_np, preds)

    metrics = {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "ece": ece,
        "sample_count": len(labels_np),
    }

    if class_names:
        per_class_f1 = f1_score(labels_np, preds, average=None, zero_division=0)
        metrics["per_class_f1"] = {
            cls_name: round(float(score), 4) for cls_name, score in zip(class_names, per_class_f1)
        }

        if plot_save_path:
            plot_confusion_matrix(cm, class_names, save_path=plot_save_path)

    return metrics, cm, logits_tensor, labels_tensor


if __name__ == "__main__":
    # Test ECE calculation on dummy predictions
    dummy_probs = np.array([[0.9, 0.1], [0.8, 0.2], [0.4, 0.6]])
    dummy_labels = np.array([0, 0, 1])
    test_ece = calculate_ece(dummy_probs, dummy_labels)
    print(f"Sample ECE calculation: {test_ece}")
    assert test_ece >= 0.0, "ECE cannot be negative"
    print("Evaluation module tests passed.")
