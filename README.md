# Moth feature discovery v5

A Streamlit proof of concept for automatically discovering **descriptive visible** moth features from photos of one species. Default: *Noctua pronuba*.

## Install
Upload `app.py`, `engine.py`, `requirements.txt` to the root of your GitHub Streamlit repository. Keep `OPENAI_API_KEY = "..."` in Streamlit **Secrets**, never in GitHub. `streamlit run app.py` locally.

## Workflow
Fetch iNaturalist research-grade observations from distinct observers, download larger images, then (on explicit button click) describe up to 12 images individually **without sending the species name**. Group recurring descriptions, and independently check up to three candidate features on up to 12 held-out images. Draw a PNG only for features supported in at least five held-out photos and at least 70% of evaluable cases. All processing after pressing the button is automatic. 'Unknown' is not a negative.

## Limitations
This is not a biological identification key. An LLM can still rely on latent training knowledge, even when instructed not to. It may hallucinate details or image coordinates. iNaturalist research-grade IDs may be wrong. Photo licensing must be checked before public use. There is no segmentation or geometric registration in this version. It is a deliberately small experiment.

## Budget
The internal stop is US$3.75 estimated for **this deployment** only, with a US$0.15 in-flight reserve. The estimate is conservative and not an enforceable billing cap. It does not incorporate previous v2–v4 API usage, and Streamlit local storage may reset. **Keep API auto-reload OFF, check the actual OpenAI prepaid balance before running, and do not increase prepaid credit.** For an actual hard limit across deployments you would need an external authoritative billing control; this app cannot guarantee an absolute €5 maximum.
