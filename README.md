# SearchSense MVP (ABHIKALP 2026 · Team Outliers)

Agentic AI mode for an e-commerce search bar.
- **Layer 1, search agent:** light router (7 stages) → Gemini intent agent → context tools (weather, occasion rules) → catalog search → verifier with constraint relaxation → clarifier (one question, only when needed).
- **Layer 2, fit & return-risk:** fit agent (size + confidence, with one fit question when confidence is low), honest notes from reviews, and a pre-checkout check with a bracketing guard. It runs on every product, whatever the search path.

Demo catalog of 25 illustrative products (fashion, lifestyle, personal care).

## Run locally
```
pip install -r requirements.txt
export GEMINI_API_KEY=your_key      # optional; without it the app uses offline rules
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud (public link)
1. Create a GitHub repo (public or private) and upload these files: `app.py`, `agent.py`, `catalog.py`, `requirements.txt`, `.streamlit/config.toml`.
   Do NOT upload `.streamlit/secrets.toml`.
2. Go to share.streamlit.io → sign in with GitHub → **Create app** → pick the repo, branch `main`, main file `app.py`.
3. Open **Advanced settings → Secrets** and paste:
   ```
   GEMINI_API_KEY = "your-key-from-aistudio.google.com"
   GEMINI_MODELS = "gemini-flash-latest,gemini-flash-lite-latest,gemini-2.5-flash"
   ```
4. Deploy. Share the `*.streamlit.app` URL. Make sure the app's sharing is set to **public**.

## Notes
- The model list is tried in order; if one fails (quota, wrong name) the next is used, then offline rules. The sidebar shows which model answered.
- Check the exact model names available to your key in Google AI Studio and edit `GEMINI_MODELS` if needed.
- Identical queries are cached for an hour, so repeated demo searches don't use quota.
