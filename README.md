# Moth visual structures v6

Technical proof of concept for a single species. Runs with **no OpenAI API key and no OpenAI charges**. Automatically downloads Research Grade iNaturalist photographs, estimates the central foreground with GrabCut, and marks locally dark image regions. It produces overlay PNGs and machine-readable measurements. No manual decisions are required to run it.

## Deployment

Upload `app.py`, `vision.py`, `requirements.txt` to a GitHub repository and point Streamlit Community Cloud to `app.py`. Existing Streamlit Secrets can remain but are not read by this app. No hidden folders are needed.

## Scientific limitations

This is an **engineering test**, not a working moth-part segmentation or species recognition model. GrabCut assumes the moth is a central foreground object and may select walls, shadows, or other objects. Dark-region detection can mark texture, shading, or dirt; numbers/positions are not yet consistent morphological landmarks. Green outline = estimated foreground, red rings = local contrast components. Do not interpret these as diagnostic features. The next phase should use an independently evaluated insect segmentation model and alignment before deriving cross-photo feature recurrence. Research Grade identifications can be wrong. Respect the license and attribution listed with each observation.
