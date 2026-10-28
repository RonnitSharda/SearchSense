# SearchSense MVP (ABHIKALP 2026 · Team Outliers)

Agentic AI mode for an e-commerce search bar.
- **Layer 1, search agent:** light router (7 stages) → Gemini intent agent → context tools (weather, occasion rules) → catalog search → verifier with constraint relaxation → clarifier (one question, only when needed).
- **Layer 2, fit & return-risk:** fit agent (size + confidence, with one fit question when confidence is low), honest notes from reviews, and a pre-checkout check with a bracketing guard. It runs on every product, whatever the search path.

## Using the app
- **🏠 Shop** opens on the full catalog (filter by department and type, sort by price, "Show more"). Search from the top bar: short queries use normal keyword search (with spelling fixes such as *sari → saree*), descriptive ones go to the AI agent.
- **🧪 Test cases** has nine scripted shoppers (Rohan, Priya, Ananya, Ambiguous, No exact match, Lifestyle, Skincare, Order help, Follow-up). Each **Run test** button runs the case and opens the results.
- **🧠 AI trace** shows every step of the last search: router decision, spelling fixes, model call, context tools, verifier attempts, a per-result constraint table and the structured intent. The sidebar toggle "Show agent trace" also shows a compact trace under the results.

## What is real and what is simulated
The catalog is **24 hand-written demo products** (so the scripted scenarios stay reliable) plus **about 5,200 real Myntra listings** (`data/myntra_catalog.csv.gz`).

| | Source |
|---|---|
| Real, from the dataset | product title, brand, price (INR), gender, first product image URL |
| Derived by keyword rules (approximate) | type, style (ethnic/western), colour and colour family, fabric, occasions, time of day, silver/gold pairing, a few notes taken from the description |
| **Simulated** | sizes available, `fit_signal` (runs small / true / large) and the number of fit reviews |
| Not in the data, so left empty | ratings, MRP / discount, shopper reviews. Rated demo products rank above unrated ones. |

**The fit agent's inputs are simulated.** The Kaggle data has no fit reviews or sizes, so `build_catalog.py` generates them deterministically per product (a "slim fit" title makes "runs small" more likely, and so on). The app says so in the product page, the sidebar and the agent trace. Treat the size recommendations as a demonstration of the mechanism, not of real accuracy. The 24 demo products are illustrative too: their prices, reviews and fit data are made up.

## Data source
Product listings come from the Kaggle dataset [`nirokey/myntra-fashion-products`](https://www.kaggle.com/datasets/nirokey/myntra-fashion-products) (12,491 rows; unmodified copy in `data/myntra_fashion_products.csv.gz`). Product names, brands, prices and images belong to Myntra and the respective brands. This repo is a non-commercial case-competition prototype; image files are not copied here, the app only links to the image URLs from the dataset. Check the licence shown on the Kaggle dataset page before using the data for anything beyond the demo. Kids' products, out-of-stock rows, duplicate titles, footwear, bags, jewellery and innerwear are dropped, and large types are capped so the catalog stays balanced (see `build_catalog.py`).

To rebuild after changing the rules (standard library only):
```
python build_catalog.py             # data/myntra_fashion_products.csv.gz -> data/myntra_catalog.csv.gz
```
If `data/myntra_catalog.csv.gz` is missing or unreadable, the app falls back to the 24 demo products.

Search over the larger catalog uses numpy indices built at start-up (a query takes a few milliseconds). Results are capped at two per brand so one label does not fill the page.

## Tests
```
python tests/test_search.py         # scenarios, vectorised-vs-reference search, speed, demo-only fallback
```

## Run locally
```
pip install -r requirements.txt
export GEMINI_API_KEY=your_key      # optional; without it the app uses offline rules
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud (public link)
1. Create a GitHub repo (public or private) and upload these files: `app.py`, `ui.py`, `agent.py`, `catalog.py`, `requirements.txt`, `.streamlit/config.toml` and the `data/` folder (`data/myntra_catalog.csv.gz` is the only data file the app needs; `build_catalog.py` and the raw export are only for rebuilding).
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
