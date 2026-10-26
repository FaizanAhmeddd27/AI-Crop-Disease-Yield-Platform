# ADR-0014: Production Disease Model Selection (EfficientNet-B0)

- **Status:** Accepted (Fulfills Milestone M2, Task 2.12)
- **Date:** 25 Oct 2026
- **Deciders:** project owner, ML engineer
- **Affects:** ARCH §2, §6.1, §6.4; SRS §3.1 (FR-D), §5.1 (NFR-P-001), §5.8 (NFR-ML-001); DEV_PLAN Phase 2 (M2) and Phase 5 (Backend)

---

## 1. Context

In Phase 2, we conducted a systematic comparative experimental matrix across 6 model configurations on the 38-class PlantVillage dataset (with held-out test splits and real-world PlantDoc field evaluations):
1. **D-01:** Baseline 4-stage CNN from scratch (reference floor).
2. **D-02:** ResNet-50 (fine-tuned ImageNet).
3. **D-03:** EfficientNet-B0 (fine-tuned ImageNet with basic augmentation).
4. **D-04:** Vision Transformer ViT-B/16 (fine-tuned ImageNet with basic augmentation).
5. **D-05:** EfficientNet-B0 with strong augmentation (lighting, cutout, color jitter).
6. **D-06:** EfficientNet-B0 with strong augmentation + label smoothing (0.1).

Our production serving constraint is **CPU-only inference** on low-cost / free-tier cloud containers (Render / Hugging Face Spaces / small VMs) with limited memory ($\le 2\text{ GB}$ RAM) and strict latency targets ($p95 \le 3\text{ s}$, NFR-P-001).

---

## 2. Experimental Comparison Matrix

| Exp ID | Architecture | Parameters | Model Size (float32) | Val Macro-F1 | Test Accuracy | CPU Latency (p95) | Calibration ECE |
|---|---|---|---|---|---|---|---|
| **D-01** | Baseline CNN (scratch) | 1.2M | 4.8 MB | 0.812 | 82.4% | 38 ms | 0.124 |
| **D-02** | ResNet-50 | 23.5M | 97.8 MB | 0.981 | 98.4% | 420 ms | 0.052 |
| **D-03** | EfficientNet-B0 (basic) | 4.0M | 21.4 MB | 0.978 | 98.1% | 135 ms | 0.048 |
| **D-04** | ViT-B/16 (Transformer) | 85.8M | 343.2 MB | 0.985 | 98.6% | 1,780 ms | 0.044 |
| **D-05** | EfficientNet-B0 (strong aug) | 4.0M | 21.4 MB | 0.980 | 98.3% | 135 ms | 0.041 |
| **D-06** | **EfficientNet-B0 (regularized)** | **4.0M** | **21.4 MB** | **0.982** | **98.4%** | **135 ms** | **0.034** |

---

## 3. Decision

We select **D-06: EfficientNet-B0 (trained with strong augmentation and label smoothing)** as the **production disease detection model** for deployment in AgriSense AI.

### Rationale:
1. **Pareto-Optimal CPU Serving:**
   - EfficientNet-B0 achieves **98.4% test accuracy** and **0.982 Macro-F1** on PlantVillage—matching ResNet-50 and falling within ~0.2% of the massive ViT-B/16.
   - It requires only **4.0 million parameters (21.4 MB)** compared to 23.5M (97.8 MB) for ResNet-50 and 85.8M (343 MB) for ViT-B/16.
   - At **135 ms CPU inference latency**, it easily outperforms `NFR-P-001` ($\le 3,000\text{ ms}$ target), leaving ample headroom for running Grad-CAM heatmaps and severity segmentation within a sub-second response.
2. **Container RAM Footprint:**
   - Loading EfficientNet-B0 into PyTorch memory consumes $< 150\text{ MB}$ of resident RAM, guaranteeing the backend stays well beneath the 1 GB–2 GB container limits.
3. **Superior Calibration (ECE = 0.034):**
   - Incorporating label smoothing ($0.1$) mitigates overconfident predictions on out-of-distribution / ambiguous inputs, providing honest probability scores for the confidence gate ($\tau = 0.60$).
4. **Grad-CAM Compatibility:**
   - The final convolutional block (`model.features[-1]`) generates sharp, localized class activation maps on lesions without requiring token reshaping operations.

---

## 4. Consequences

### Positive:
- **Fast Cold Starts & Minimal Egress:** A 21 MB model artifact downloads in $< 2\text{ seconds}$ from Supabase Storage during backend startup.
- **High Concurrency on Free Tiers:** Low CPU and memory requirements allow multiple concurrent prediction requests on a single container without OOM kills.
- **Reproducibility:** The exact run record, weights, preprocessing config, and label maps are preserved under `artifacts/runs/` and promoted to `models/disease/v1.0.0/`.

### Negative & Mitigations:
- **Lab-to-Field Domain Gap:** Like all models trained primarily on PlantVillage, accuracy drops on real-world field images (PlantDoc benchmark: ~68.4% F1).
  - *Mitigation:* Strong augmentations in D-05/D-06 narrow this gap. In the UI, predictions with confidence $< 0.60$ trigger an `uncertain` guidance banner rather than an ungrounded diagnosis, and clear disclaimers state that outputs are decision support only.
