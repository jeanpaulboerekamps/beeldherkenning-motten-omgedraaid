# Moth comparison lab

Streamlit prototype for side-by-side inspection of research-grade iNaturalist moth observations, exploratory color statistics, blinded human character notes, and annotated recognition cards.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

Upload `app.py` and `requirements.txt` to a GitHub repository. Select `app.py` as the entry point in Streamlit Community Cloud.

## Scientific limitations

This version does **not** automatically infer reliable anatomical diagnostic features. Simple image statistics are exploratory and can be confounded by lighting and backgrounds. Photo annotation is manual. Confirm candidate characters against multiple individuals and literature after recording blind hypotheses. Research Grade is not infallible. Respect individual photo licenses and credits.
