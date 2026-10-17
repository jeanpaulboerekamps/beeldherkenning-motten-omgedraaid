# Moth Comparison Lab v3

Streamlit application for a **fully automated** experiment in distinguishing two moth species by photographs alone. No field guide is provided to the model, and no manual annotation or acceptance is required.

## Setup

Upload `app.py`, `ai_pipeline.py`, `requirements.txt` to your GitHub repository root. Set the Streamlit main file to `app.py`. In Streamlit app settings → Secrets enter:

```toml
OPENAI_API_KEY = "your-key-here"
```

Fetch at least 16 photographs per species. Press **Run fully automatic discovery and validation** once. The workflow uses 8 discovery photos and 8 independent held-out photos per species. It examines images in small groups, proposes up to three binary traits, independently tests each trait on held-out images, and only annotates traits passing a pre-specified criterion (≥6 evaluable per species, ≥75% yes in positive group, ≤25% yes in negative group). The localization step is still approximate; the generated cards are labeled experimental.

## Spending safeguards

The goal is €5 for the entire experiment, **not a guaranteed billing cap**. The application reserves US$0.18 for each attempted model call in `data/ai_budget_v3.json` and stops once the cumulative reservation would exceed US$4. This file persists across sessions only while Streamlit's local filesystem survives. Redeploys/restarts can reset it. API charges from other apps are not counted. Set your own billing controls, keep auto-reload off, and check actual remaining credit before rerunning. Previous v2 API usage is not imported into this ledger. A full run may use up to 20 model calls, reserving up to US$3.60. API charges can differ from these reservations. There is no guarantee that the complete run stays below €5 in all circumstances.

No automated claim is a verified diagnostic character; iNaturalist Research Grade labels can be incorrect, and camera angles, sexual dimorphism, variation, and wear affect conclusions. Photo licenses must be reviewed before redistribution.
