# Moth Comparison Lab v4

Automated image-by-image candidate discovery and independent hold-out validation for two iNaturalist moth species. No human annotation is needed.

## Deploy
Upload `app.py`, `ai_pipeline.py`, `ai_discovery.py`, and `requirements.txt` to GitHub, then deploy `app.py` on Streamlit. Store `OPENAI_API_KEY` only in Streamlit Secrets. Never commit your key.

## Budget
The app now releases temporary per-request reservations after successful API responses and tracks estimated token cost, instead of treating all reservations as spent. It reads a legacy v3 ledger *if that file still exists*, but a Streamlit redeploy may erase local files. It cannot retrieve actual billing, and it cannot guarantee a hard €5 ceiling. The user must verify remaining prepaid balance on the OpenAI platform; leave auto-reload OFF. An API error is conservatively charged at the full $0.18 reservation. Do not increase credit or rerun automatically.

## Limitations
AI features are unverified hypotheses, not reliable identification characters. Images are sent to the OpenAI API. iNaturalist image rights and attribution must be respected. The pipeline was syntax-tested but not live-tested with an API key.
