# Moth Comparison Lab v2

Streamlit application for experimental **automatic** comparison of *Noctua comes* and *N. interjecta* from iNaturalist research-grade photos.

## Deploy
Upload `app.py`, `ai_discovery.py`, `requirements.txt` to the repository root; select `app.py` as the Streamlit entry point. Do not upload `__pycache__` or API credentials.

In Streamlit Community Cloud → App settings → Secrets add:

```toml
OPENAI_API_KEY = "sk-..."
```

Fetch photos, then choose **Automatic AI discovery** → **Discover distinguishing features automatically**. The app uses at most 20 images per species for the AI comparison, even if more are fetched for visual review.

## Cost and safety

The user's experiment target is **€5 total**. The app has an intentionally conservative internal **US$4 ceiling**, with a US$1 reservation for each attempted analysis and an approximate token-based usage meter. This is **not a guaranteed or durable spending cap**: Streamlit session state can reset, other API calls are not counted, prices and FX change, and API billing can differ from local estimates. Configure API project budget/alerts at platform.openai.com and monitor actual usage. Do not rely on the app alone to enforce €5.

No AI request is made by merely fetching photos. Only clicking the AI button incurs OpenAI API usage. One AI request is sent per click. Model: `gpt-4.1-mini`. The estimate uses conservative internal rates (not official price quotes) of $1 / 1M input tokens and $6 / 1M output tokens.

## Scientific caveats

The model sees two labeled contact sheets and receives no species descriptions. Results are tentative, not validated diagnostic characters. Photo backgrounds, misidentifications, variability, perspective and lighting can mislead. The coordinates used for annotations are approximate, and may be wrong. Photos and attributions come from iNaturalist; check each photo's license before publication.
