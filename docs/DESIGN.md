---
version: "superdesign-alpha"
name: "CropSense Minimal"
description: "A quiet, flat, leaf-tinted editorial landing page. Forest and leaf only, one oversized sans headline with a single serif-italic accent, generous whitespace, no gradients and no decoration that doesn't carry meaning."
colors:
  forest: "#064734"
  leaf: "#E0FFC2"
  background: "#F4FFE9"
  surface: "#FFFFFF"
  text-primary: "#06241B"
  text-secondary: "#5E7A6E"
  border: "#C6E3AE"
  status-healthy: "#2E9E5B"
  status-warning: "#F2B53A"
  status-danger: "#D9453B"
typography:
  display-lg:
    fontFamily: "Figtree"
    fontSize: "80px"
    fontWeight: 500
    lineHeight: "0.95"
    letterSpacing: "-3px"
  headline-md:
    fontFamily: "Figtree"
    fontSize: "48px"
    fontWeight: 500
    lineHeight: "1.02"
    letterSpacing: "-1.5px"
  body-md:
    fontFamily: "Figtree"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: "1.4"
  body-sm:
    fontFamily: "Figtree"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "1.5"
  accent-serif:
    fontFamily: "Instrument Serif"
    fontStyle: "italic"
  label-mono:
    fontFamily: "JetBrains Mono"
    fontSize: "12px"
    letterSpacing: "0.08em"
    textTransform: "uppercase"
spacing:
  base: "8px"
  gap-md: "24px"
  gap-lg: "48px"
  section-padding: "120px"
  container: "1120px"
rounded:
  control: "8px"
  panel: "20px"
  chip: "9999px"
components:
  button-primary:
    background: "#064734"
    text-color: "#E0FFC2"
    radius: "8px"
    height: "52px"
    padding: "0 24px"
    hover-background: "#E0FFC2"
    hover-text-color: "#064734"
    hover-border: "1px solid #064734"
  button-ghost:
    background: "transparent"
    text-color: "#064734"
    radius: "8px"
    height: "52px"
    border: "1px solid #064734"
    hover-background: "#FFFFFF"
  panel-forest:
    background: "#064734"
    text-color: "#E0FFC2"
    radius: "20px"
  panel-leaf:
    background: "#E0FFC2"
    text-color: "#064734"
    radius: "20px"
---
# CropSense Minimal
AI-Powered Crop Disease & Yield Prediction Platform. Landing page design system.
Theme: **Forest `#064734`** and **Leaf `#E0FFC2`**.

> "CropSense" is a working name. Replace it once the final name is decided.

## Principles
This page should feel like a well-set magazine page, not a SaaS template. Every element has to earn its place.

1. **Two colours, flat.** Forest and leaf, on a pale leaf-tinted page. No gradients, no glows, no glass, no shadows beyond a hover lift.
2. **One idea per section.** A headline, a few lines of copy, one visual. Nothing else.
3. **Type does the work.** Big Figtree headlines, one serif-italic accent per headline, mono labels. No icon circles, no emoji, no stock illustration.
4. **Honest content.** No fake stats, testimonials, logos or accuracy numbers. The only visuals are the product's real outputs (a leaf with Grad-CAM, a SHAP chart), clearly marked as sample until real results exist.
5. **Whitespace is the design.** 120px between sections, left-aligned layouts, large margins.

## Colors
- **Forest `#064734`**: text on light, primary buttons, the hero panel, the footer.
- **Leaf `#E0FFC2`**: text on forest, the second panel, chips, progress tracks.
- **Page `#F4FFE9`** (a lighter leaf tint so the page doesn't feel neon) and **white `#FFFFFF`** for result cards.
- **Ink `#06241B`** for body copy, **`#5E7A6E`** for secondary text, **`#C6E3AE`** for hairlines.
- **Status colours** (`#2E9E5B`, `#F2B53A`, `#D9453B`) appear **only** on severity and risk badges inside result cards. Never as decoration.

Proportion: about 75% page and white, 20% forest, 5% leaf.

## Typography
- **Figtree** for everything: display 80px / headline 48px / body 19px / small 14px, with tight negative tracking on headlines.
- **Instrument Serif Italic** on **one short clause (2-4 words) per headline**, e.g. "Detect disease *early*."
- **JetBrains Mono**, 12px, uppercase, wide tracking for small labels and step numbers.
- Mobile: display 44px, headline 32px.

## Layout
Container 1120px, left-aligned. Headlines are left-aligned (centre only the footer headline if at all). Two-column splits use roughly 55/45. Panels use a 20px radius; buttons 8px. No other radii.

## Page Structure
Six sections. Nothing more.

### 1. Navbar
Wordmark left. Three text links: *Detect*, *Forecast*, *How it works*. One primary button on the right: "Try it". No secondary button, no login.

### 2. Hero
- Label (mono): `AI FOR CROP HEALTH`
- Headline: "Detect disease *early.* Forecast yield before harvest."
- One line of support: "Upload a leaf photo or enter your farm details. Get a diagnosis or a yield forecast, with the reasoning shown."
- Two buttons: primary "Scan a leaf", ghost "Forecast yield".
- **Right side: one flat forest panel** holding a single sample result card (white, 12px radius): leaf photo with Grad-CAM overlay, disease name, confidence bar (forest on leaf track), severity badge. Labelled `SAMPLE`. This is the page's only product visual in the hero.

### 3. Two Tools
Two large panels side by side, one `panel-forest`, one `panel-leaf`. Each contains only:
- Mono label, a headline, three short lines, one text link with arrow.

**Disease detection**: upload a leaf, get the disease, a confidence score and a severity level, with Grad-CAM showing where the model looked. Recommended actions come from a trusted agricultural source.
**Yield prediction**: enter your crop, location and farm details, weather and soil data are pulled in, get a predicted yield and a risk level with SHAP showing the main factors.

### 4. How It Works
Three steps in a plain row, separated by hairlines. **No cards, no icons.** Each is a mono number (`01`, `02`, `03`), a short title and one sentence:
1. **Add your data**: a leaf photo, or your crop and location.
2. **The model runs**: image classifier or yield forecaster, using weather and soil data.
3. **See why**: the result, plus the explanation behind it.

### 5. Explainable AI
Headline: "Every answer comes with its *reasoning*." Two white result cards side by side, each with a real-looking sample output and a one-line caption:
- **Grad-CAM**: leaf with heatmap. "Shows which parts of the leaf drove the diagnosis."
- **SHAP**: horizontal bar chart in forest and leaf. "Shows which weather, soil and history drove the forecast."

Heatmap keeps its standard blue-to-red scale because it is data. Both marked `SAMPLE`.

### 6. Footer / Final CTA
Solid forest band. Large leaf-coloured headline: "Healthier crops, *clearer harvests.*" One leaf-filled primary button ("Try it"). Below, a single muted line of tech: `PyTorch · FastAPI · Next.js · Supabase · MLflow`. Then a small link row (GitHub, Docs, Contact) and the project name.

## Components
- **Primary button**: forest fill, leaf text, 8px radius, 52px tall. Hover inverts to leaf fill, forest text, 1px forest border. (On the forest footer the button is reversed: leaf fill, forest text.)
- **Ghost button**: transparent, 1px forest border, hover fills white.
- **Panels**: flat forest or flat leaf, 20px radius, generous padding (48px).
- **Result card**: white, 12px radius, 1px `#C6E3AE` border, no shadow. Severity badge is a pill with the status colour at 15% fill and full-colour text.
- **Progress / confidence bar**: forest fill on a leaf track, 8px tall, fully rounded.
- **Text link**: forest, underline on hover, trailing arrow.
- **Hairline**: 1px `#C6E3AE`.

## Motion
Hover swaps only (`0.2s ease` on colour and background). Sections fade up 12px on scroll, once. No parallax, no marquee, no looping animation. Loading states use a simple forest bar, not a spinner.

## Removed On Purpose
These were cut to keep the page minimal. Do not add them back:
- Gradient tiles, mesh gradients, glow overlays, glass badges, embossed button shadows
- Platform overview chips, dashboard preview, data-source logo strip
- Model comparison and metrics panel (keep this for the README or a separate docs page)
- Tech-stack tile carousel (reduced to a single line in the footer)
- Roadmap chip cluster, FAQ accordion, secondary CTA card
- Icon-in-circle feature cards, stat counters, testimonials, pricing

## Guardrails
- One accent serif clause per headline, never a whole headline.
- Never use more than forest, leaf, white and the page tint in a single section.
- Status colours only on badges, never on surfaces or buttons.
- Keep text contrast high: forest on leaf or white, leaf on forest. Never leaf on white.
- No invented numbers. Use `SAMPLE` labels or `—` until real results exist.
- Disease recommendations are presented as sourced guidance, never as model-generated advice.
