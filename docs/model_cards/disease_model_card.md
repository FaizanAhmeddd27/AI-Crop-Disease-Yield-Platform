# Model Card: AgriSense AI Crop Leaf Disease Classifier

| Field | Value |
|---|---|
| Model Name | EfficientNet-B0 Disease Classifier |
| Version | `v1.0.0` |
| Pipeline | Disease Detection (Computer Vision) |
| Architecture | EfficientNet-B0 (Transfer Learning from ImageNet) |
| Date | 25 Oct 2026 |
| Maintainers | AgriSense AI ML Engineering Team |
| License | MIT / Academic Open Source |

---

## 1. Model Details
- **Base Architecture:** `torchvision.models.efficientnet_b0` fine-tuned with modified 38-class linear classification head.
- **Parameters:** 4,049,566 (~4.0M) parameters.
- **Model Size:** 21.4 MB (float32 TorchScript/PyTorch checkpoint), ~11 MB in INT8 quantized representation.
- **Training Configuration:**
  - Optimizer: AdamW (learning rate = $3\times 10^{-4}$, weight decay = $1\times 10^{-4}$).
  - Scheduler: CosineAnnealingLR (10 epochs, $\eta_{min} = 3\times 10^{-6}$).
  - Loss: CrossEntropyLoss with Label Smoothing ($0.10$).
  - Augmentations: RandomResizedCrop, RandomHorizontalFlip, RandomVerticalFlip, ColorJitter, RandomRotation ($30^\circ$), RandomErasing (Cutout).
  - Mixed Precision: Automatic Mixed Precision (AMP) enabled on CUDA.

---

## 2. Intended Use
- **Primary Use Cases:**
  - Decision support tool for smallholder farmers and agricultural extension officers to identify foliar diseases early from smartphone photos.
  - Generates region-level visual explanations via Grad-CAM highlighting influential leaf lesions.
  - Interfaces with a curated knowledge base to display vetted cultural and chemical management recommendations.
- **Out-of-Scope / Prohibited Uses:**
  - Not an autonomous agrochemical sprayer controller.
  - Not certified as an official pesticide prescription system; users are explicitly instructed to confirm findings with local agronomists before chemical application.
  - Not intended for non-leaf plant parts (stems, roots, tubers, cut fruit).

---

## 3. Data & Splits
- **Primary Training & Validation Dataset:** PlantVillage (~54,303 images, 38 crop-condition classes across 14 crops).
  - Train Split (70%): 38,015 images.
  - Validation Split (15%): 8,145 images.
  - Held-out Test Split (15%): 8,143 images.
  - Seed: 42 (stratified by class, near-duplicates grouped by `dHash` to prevent leakage).
- **External Real-World Field Benchmark:** PlantDoc dataset (~2,598 images captured in active fields under natural lighting, soil backgrounds, and camera noise).

---

## 4. Performance Metrics

| Evaluation Set | Metric | Target | Result | Status |
|---|---|---|---|---|
| **PlantVillage Test** | Top-1 Accuracy | $\ge 95.0\%$ | **98.4%** | Exceeded |
| **PlantVillage Test** | Macro-F1 Score | $\ge 0.940$ | **0.982** | Exceeded |
| **PlantVillage Test** | Calibration ECE | $\le 0.050$ | **0.034** | Exceeded |
| **PlantDoc (Field)** | Macro-F1 Score | $\ge 0.600$ | **0.684** | Met |
| **CPU Serving** | p95 Latency | $\le 3,000\text{ ms}$ | **135 ms** | Exceeded |
| **Memory Footprint** | Resident RAM | $\le 2,000\text{ MB}$ | **~150 MB** | Exceeded |

---

## 5. Input & Output Specifications
- **Input:** Single RGB image (JPEG, PNG, WebP).
  - Input Preprocessing: Center crop / resize to $224 \times 224$ pixels, normalized using ImageNet statistics:
    $$\mu = [0.485, 0.456, 0.406], \quad \sigma = [0.229, 0.224, 0.225]$$
- **Output:**
  - Softmax probabilities across 38 classes.
  - Top-1 and Top-3 predicted crop and disease names.
  - Calibrated confidence score $[0.0, 1.0]$.
  - Status flag: `ok` if confidence $\ge 0.60$; `uncertain` if confidence $< 0.60$.
  - Estimated severity level (`none`, `low`, `moderate`, `severe`).
  - Grad-CAM heatmap overlay.

---

## 6. Limitations & Bias
1. **Lab-to-Field Domain Gap:** Training predominantly on controlled laboratory images (PlantVillage plain backgrounds) introduces sensitivity to field background clutter (hands, soil, weeds). Strong augmentations in D-05/D-06 mitigate this, but accuracy drops from 98.4% in the lab to 68.4% in the wild.
2. **Confidence Thresholding:** When confidence falls below 0.60, the model refuses to output a definitive diagnosis, prompting the farmer to retake the photo under clearer lighting.
3. **Class Scope:** Limited to the 38 supported crop-condition classes. Unseen diseases or non-supported crops will trigger low confidence or nearest-neighbor visual artifacts.
