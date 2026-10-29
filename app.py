import os, re, sys, time, html, json, collections, importlib, zlib, hashlib, hmac, uuid, datetime
import streamlit as st

# When new code is deployed, Streamlit unloads changed modules while other sessions may be importing them, which can
# raise KeyError('catalog') inside Python's import system. Retry the imports instead of showing the error.
for _attempt in range(5):
    try:
        from catalog import PRODUCTS, SIZE_ORDER, WAIST_ORDER, ANCHOR_BRANDS, BREATHABLE, CATALOG_SOURCE
        import agent as A
        from ui import CSS, DARK_CSS, image_block, price_block
        break
    except KeyError:
        if _attempt == 4:
            raise
        for _m in ("catalog", "prompt", "agent", "ui"):
            sys.modules.pop(_m, None)
        importlib.invalidate_caches()
        time.sleep(0.3)

st.set_page_config(page_title="SearchSense: agentic search MVP", page_icon="🔎", layout="wide")

# ------------------------------------------------------------------ config
def _secret(k, default=None):
    try:
        return st.secrets.get(k, os.environ.get(k, default))
    except Exception:
        return os.environ.get(k, default)

API_KEY = _secret("GEMINI_API_KEY")
MODELS = [m.strip() for m in _secret("GEMINI_MODELS", "gemini-flash-latest,gemini-flash-lite-latest,gemini-2.5-flash").split(",") if m.strip()]

st.markdown(CSS, unsafe_allow_html=True)
# the theme goes first on every run, before any search work, so it stays applied while results load and after.
# It is also kept in the URL (?theme=dark), so it survives a browser refresh.
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = st.query_params.get("theme") == "dark"
if st.session_state.get("dark_mode"):
    st.markdown(DARK_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------ state
S = st.session_state
S.setdefault("view", "search")
S.setdefault("cart", [])
S.setdefault("history", [])
S.setdefault("result", None)
S.setdefault("pid", None)
S.setdefault("removed_chips", [])
S.setdefault("last_results", [])
TABS = ["🏠 Shop", "📖 Tutorial", "🧪 Test cases", "🧠 AI trace", "📊 Metrics", "🔐 Admin"]
S.setdefault("tab", TABS[0])
S.setdefault("last_tab", TABS[0])
S.setdefault("home_n", 24)
S.setdefault("sid", uuid.uuid4().hex[:6])   # anonymous id, so the admin tab can tell visitors apart
S.setdefault("metrics", dict(searches=[], adds=[], nudges_shown=0, nudges_accepted=0, orders=0, ordered_items=0, flagged=set()))

# ------------------------------------------------------------------ helpers
STAGE_PILL = {0: ("0 · Pass-through", "p-grey"), 1: ("1 · Clear intent", "p-navy"), 2: ("2 · Minor correction", "p-navy"),
              3: ("3 · Major semantic", "p-pink"), 4: ("4 · Ambiguous", "p-amber"), 5: ("5 · No exact match", "p-navy"),
              6: ("6 · Out of scope", "p-grey")}

def pill(stage):
    t, c = STAGE_PILL.get(stage, (str(stage), "p-navy"))
    return f'<span class="pill {c}">{t}</span>'

def fit_badge(p):
    """Solution doc, fit confidence table: High = "Take M"; Medium = size + the main fit note; Low = never a confident guess."""
    fa = A.fit_agent(p, S.profile)
    if not fa: return ""
    if fa["size"] and fa["confidence"] == "high":
        return f'<span class="badge b-high" title="{html.escape(fa["reason"])}">Take {fa["size"]}</span>'
    if fa["size"] and fa["confidence"] == "medium":
        return f'<span class="badge b-medium" title="{html.escape(fa["reason"])}">{fa["size"]} recommended · {html.escape(fa["note"])}</span>'
    return '<span class="badge b-low">Not sure of your size · check fit</span>'


def record_add(p, size, fa):
    """Accepted-size-recommendation KPI: did the shopper keep the size we suggested? Also feeds this profile's suggestions."""
    note_behaviour("type", p["type"], 2); note_behaviour("brand", p["brand"], 1); note_behaviour("colour_family", p["colour_family"], 1)
    S.metrics["adds"].append(dict(pid=p["id"], size=size, rec=(fa or {}).get("size") if (fa or {}).get("confidence") in ("high", "medium") else None))

def risky_note(p):
    for n in p["notes"]:
        if "not see" in n.lower(): continue
        if any(w in n.lower() for w in ["runs small", "runs slightly large", "sheer", "see-through", "peach", "heavy", "creases", "fragrance", "cool white", "relaxed"]):
            return f'<span class="note">💡 {html.escape(n)}</span>'
    return ""

@st.cache_resource
def _search_log():
    """Every search by every visitor since the app started (admin tab)."""
    return collections.deque(maxlen=500)


@st.cache_resource
def _started():
    return time.time()


_started()


PRERUN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "demo_cache.json")


def _load_prerun():
    """Saved AI answers for the demo searches and product questions (see Admin → Pre-run demo), if the file exists."""
    try:
        with open(PRERUN_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return ({(q, tuple(h), prev): tuple(v) for q, h, prev, v in d.get("intents", [])},
                {(pid, q): tuple(v) for pid, q, v in d.get("qa", [])})
    except Exception:
        return {}, {}


@st.cache_resource
def _intent_cache():
    return _load_prerun()[0]


@st.cache_resource
def _qa_cache():
    return _load_prerun()[1]


def cached_understand(query, history, _key, models, previous=""):
    """Identical queries reuse the agent's answer (saves quota and latency). Failures are never cached. The key is the words,
    the previous search (for follow-ups) and nothing else, so answers saved by the demo pre-run are reused on stage."""
    import copy
    cache, key = _intent_cache(), (query, history, previous)
    if key in cache:
        intent, model, log = copy.deepcopy(cache[key])
        return intent, model, log + ["served from cache"]
    with st.spinner("✦ AI mode is reading your request…"):
        out = A.understand(query, _key, list(models), list(history), json.loads(previous) if previous else None)
    if out[1] != "failed":
        if len(cache) > 2000: cache.clear()
        cache[key] = copy.deepcopy(out)
    return out


TOP_CHART = {"XS": {"Chest (in)": 32, "Waist (in)": 26, "Shoulder (in)": 13.5}, "S": {"Chest (in)": 34, "Waist (in)": 28, "Shoulder (in)": 14},
             "M": {"Chest (in)": 36, "Waist (in)": 30, "Shoulder (in)": 14.5}, "L": {"Chest (in)": 38, "Waist (in)": 32, "Shoulder (in)": 15},
             "XL": {"Chest (in)": 40, "Waist (in)": 34, "Shoulder (in)": 15.5}, "XXL": {"Chest (in)": 42, "Waist (in)": 36, "Shoulder (in)": 16}}
WAIST_CHART = {w: {"Waist (in)": int(w), "Hip (in)": int(w) + 8, "Inseam (in)": 30} for w in WAIST_ORDER}


def mark(ok):
    """Verifier result: pass, fail, or unknown (the listing doesn't state it)."""
    return "✓" if ok else ("?" if ok is None else "✕")

def chips_from(intent):
    """Applied filters as (label, section, key), labelled like a shop's filter bar: "Gender: Men", "Colour: Yellow"."""
    h, s = intent.get("hard", {}), intent.get("soft", {})
    out = []
    if h.get("category") and h["category"] != "fashion":
        out.append((f"Category: {'Home' if h['category'] == 'lifestyle' else h['category'].title()}", "hard", "category"))
    if h.get("gender"): out.append((f"Gender: {h['gender'].title()}", "hard", "gender"))
    if h.get("types"): out.append(("Item: " + " / ".join(t.title() if t != "t-shirt" else "T-shirt" for t in h["types"]), "hard", "types"))
    if h.get("style"): out.append((f"Style: {h['style'].title()}", "hard", "style"))
    if h.get("size"): out.append((f"Size: {h['size']}", "hard", "size"))
    if h.get("budget_min") and h.get("budget_max"): out.append((f"Budget: ₹{h['budget_min']:,}–{h['budget_max']:,}", "hard", "budget"))
    elif h.get("budget_max"): out.append((f"Budget: under ₹{h['budget_max']:,}", "hard", "budget"))
    elif h.get("budget_min"): out.append((f"Budget: over ₹{h['budget_min']:,}", "hard", "budget"))
    if s.get("colours"): out.append(("Colour: " + " / ".join(s["colours"]).title(), "soft", "colours"))
    if s.get("colour_family"): out.append(("Colours: " + " / ".join(s["colour_family"]).title(), "soft", "colour_family"))
    if s.get("fabrics"): out.append(("Fabric: " + ", ".join(sorted(s["fabrics"])[:4]) + ("…" if len(s["fabrics"]) > 4 else ""), "soft", "fabrics"))
    if s.get("occasion"): out.append((f"Occasion: {s['occasion'].title()}", "soft", "occasion"))
    if s.get("time") and s["time"] != "any": out.append(("Time: " + ("Daytime" if s["time"] == "day" else "Evening"), "soft", "time"))
    if s.get("pairs") and s["pairs"] != "any": out.append((f"Pairs with: {s['pairs'].title()}", "soft", "pairs"))
    for n in s.get("needs") or []: out.append((f"Need: {n}", "soft", "needs:" + n))
    return out


def kw_chips(f):
    """Filters a normal search applied, as (label, kind, value)."""
    out = []
    if f.get("gender"): out.append((f"Gender: {f['gender'].title()}" + (" (your profile)" if f.get("gender_from") == "profile" else ""), "gender", f["gender"]))
    for t, _ in f.get("types", []): out.append((f"Item: {'T-shirt' if t == 't-shirt' else t.title()}", "type", t))
    if f.get("colours"): out.append(("Colour: " + " ".join(c for c, _ in f["colours"]).title(), "colour", " ".join(c for c, _ in f["colours"])))
    if f.get("size"): out.append((f"Size: {f['size']}", "size", f["size"]))
    for w in f.get("words", []):
        out.append(((f"Fabric: {w.title()}" if w in A.ALLOWED["fabrics"] else f"Keyword: {w}"), "word", w))
    return out


def describe(gender=None, colours=(), types=(), size=None, extra=(), budget="", style=None, category=None):
    """'Men's yellow t-shirts in size M' from structured filters."""
    who = {"men": "Men's ", "women": "Women's "}.get(gender or "", "")
    item = " / ".join(("t-shirts" if t == "t-shirt" else t + ("s" if not t.endswith("s") else "")) for t in types)
    if not item:
        item = {"lifestyle": "home products", "personal care": "beauty products"}.get(category or "", "outfits" if style or gender else "products")
        if style in ("ethnic", "western"): item = f"{style} {item}"
    words = " ".join([*colours, *extra])
    return f"{who}{words + ' ' if words else ''}{item}{' in size ' + size if size else ''}{budget}".strip()


def bubble(typed, understood, why, showing):
    """The reasoning layer: You typed -> I understood -> so I'm showing."""
    why_html = f'<div class="b-why">{" · ".join(html.escape(w) for w in why)}</div>' if why else ""
    st.markdown(f'<div class="bubble"><div class="b-ic">✦</div><div class="b-body">'
                f'<div class="b-row"><span class="b-k">You typed</span><span class="b-v">“{html.escape(typed)}”</span></div>'
                f'<div class="b-row"><span class="b-k">I understood</span><span class="b-v"><b>{html.escape(understood)}</b>{why_html}</span></div>'
                f'<div class="b-row"><span class="b-k">So I’m showing</span><span class="b-v">{showing}</span></div>'
                f'</div></div>', unsafe_allow_html=True)


def apply_removed(intent, removed):
    import copy
    it = copy.deepcopy(intent)
    for label, sec, key in chips_from(intent):
        if label in removed:
            if key.startswith("needs:"):
                it["soft"]["needs"] = [n for n in it["soft"].get("needs", []) if n != key[6:]]
            elif key == "budget":
                it["hard"]["budget_min"] = it["hard"]["budget_max"] = None
            elif key == "category":
                it["hard"]["category"] = None
            else:
                it[sec][key] = [] if isinstance(it[sec].get(key), list) else None
    return it

# ------------------------------------------------------------------ core run
def resolve_followup(q):
    """'#2 but cheaper' -> add the referenced product's details for the agent."""
    m = re.search(r"#(\d)", q)
    if m and S.last_results:
        i = int(m.group(1)) - 1
        if 0 <= i < len(S.last_results):
            p = PRODUCTS[S.last_results[i]]
            extra = f" (refers to result #{i+1}: {p['name']}, {p['type']}, {p['fabric']}, {p['colour']}, ₹{p['price']})"
            q2 = q + extra
            if "cheaper" in q.lower():
                q2 += f" budget under {p['price'] - 1}"
            return q2
    return q

def run_search(q, followup=False, exact=False):
    t0 = time.time()
    S.search_seq = S.get("search_seq", 0) + 1
    A.set_log_tag(f"{S.sid}-{S.search_seq}")   # Gemini calls made during this search carry this id (admin tab)
    S.removed_chips = []
    q_in = resolve_followup(q) if followup else q
    r = A.route(q_in if followup else q, ai=bool(API_KEY))
    if exact:   # one-tap undo: search the shopper's exact words, no corrections, no AI
        r = dict(stage=0, label="Undo: your exact words", query=q, fixes=[], reason="Searching your exact words, without spelling fixes")
    if followup and r["stage"] in (0, 2):
        r = dict(stage="agent", label="Follow-up: sent to agent with context", query=q_in, fixes=[], reason="Refinement of the previous search")
    res = dict(query=q, route=r, steps=[], t=0)
    if r["stage"] == 6:
        res.update(kind="help", qtype="support")
        res["steps"].append(("Hand-off", "help_desk()", "Customer-support request (router): no product search, sent to Customer Care / Help chat"))
    if r["stage"] in (0, 2):
        fixes = ", ".join(f"“{a}” → “{b}”" for a, b in r.get("fixes", [])) or "no spelling changes"
        res["steps"].append(("Spell check", "correct_tokens()", f"{fixes}; searching for “{r['query']}”"))
        g = A.query_gender(r["query"]) or S.profile.get("gender")
        info = {}
        items = A.keyword_search(r["query"], max_results=24, gender=S.profile.get("gender"), info=info)
        res["steps"].append(("Keyword search", f"keyword_search(gender={g or 'any'})",
                             f"{len(items)} matches; required words: {', '.join(info.get('words', [])) or 'none'} ({info.get('mode', '')}; "
                             "a colour also accepts close shades)" + (f"; fashion limited to {g} + unisex" if g else "")
                             + ". No AI call: short, specific queries skip Layer 1"))
        if items or not API_KEY or exact:
            res.update(kind="keyword", items=[p["id"] for p in items], kw_info=info,
                       kw_filters=A.keyword_filters(r["query"], S.profile.get("gender")))
            S.history.append(f"{r['query']} -> normal search")
            S.last_results = res["items"]
        else:   # nothing matched the words: let the agent work out what the shopper meant
            res["steps"].append(("Escalation", "route()", "No keyword match, so the query goes to the AI agent"))
            r = res["route"] = dict(stage="agent", label="No keyword match: sent to agent", query=q, fixes=[],
                                    reason="Keyword search found nothing; the agent interprets the request")
    if r["stage"] == "agent":
        hist = tuple(S.history[-1:]) if followup else tuple()   # a follow-up refines the previous search only
        prev = None
        if followup and S.result and S.result.get("kind") == "agent":
            prev = S.result.get("intent")
        elif followup and S.result and S.result.get("kind") == "keyword" and S.result.get("kw_filters"):
            kf = S.result["kw_filters"]   # a normal search's filters become the previous constraints
            prev = {"hard": {"gender": kf.get("gender"), "types": [t for t, _ in kf.get("types", [])], "size": kf.get("size")},
                    "soft": {"colours": [c for c, _ in kf.get("colours", [])]}}
        t_ai = time.time()
        intent, model, log = cached_understand(r["query"], hist, API_KEY, tuple(MODELS),
                                               json.dumps(prev, ensure_ascii=False, default=str) if prev else "")
        res.update(t_ai=time.time() - t_ai, model=model, ai_log=log)
        res["steps"].append(("Intent & constraints", f"model: {model}", "; ".join(l for l in log if not l.startswith("validator:"))
                             + ("; previous search's constraints passed as context" if prev else "")))
        if model == "failed":   # safety net: the shopper is never worse off than normal search
            items = A.keyword_search(q, max_results=24, gender=S.profile.get("gender"))
            res["steps"].append(("Safety net", "keyword_search()", f"AI unavailable ({'; '.join(log)[:160]}), so the original query "
                                 f"ran on normal search: {len(items)} matches"))
            res.update(kind="keyword", items=[p["id"] for p in items], fallback=True,
                       route=dict(r, stage=0, label="Safety net: normal search", reason="AI unavailable; normal search used"))
            S.last_results = res["items"]
            res["t"] = time.time() - t0
            S.result, S.view = res, "search"
            record_search(res)
            return
        res["steps"].append(("Validator", "validate_intent()", next((l[11:] for l in log if l.startswith("validator:")), "")))
        qt = intent.get("query_type", "product_search")
        res["steps"].append(("Query type", "classify()", f"{qt}" + (f" · reply: “{intent['reply']}”" if intent.get("reply") else "")))
        if qt in ("support", "other"):   # the agent recognised a message that is not a product search
            res["steps"].append(("Hand-off", "help_desk()" if qt == "support" else "redirect()",
                                 f"{'Customer-support request' if qt == 'support' else 'Not a shopping request'} (agent): {intent.get('interpretation', '')}"))
            res.update(kind="help", qtype=qt, intent=intent, model=model, route=dict(r, stage=6))
            res["t"] = time.time() - t0
            S.result, S.view = res, "search"
            record_search(res)
            return
        h = intent.setdefault("hard", {})
        if not h.get("gender") and h.get("category", "fashion") in (None, "fashion") and S.profile.get("gender"):
            h["gender"] = S.profile["gender"]
            res["steps"].append(("Profile", "shopping_for", f"gender = {h['gender']} (from account)"))
        intent, calls = A.enrich(intent)
        for name, arg, out in calls:
            res["steps"].append(("Context tool", f"{name}({arg})", out))
        res.update(kind="agent", intent=intent, model=model)
        if intent.get("stage") == 4 and intent.get("clarify"):
            res["steps"].append(("Clarifier", "stage 4", intent["clarify"]["question"]))
        items, relaxed, trace, near = A.search(intent, max_results=8)
        for t in trace: res["steps"].append(("Catalog search + verifier", "catalog_search()", t))
        if relaxed and intent.get("stage") != 4:
            intent["stage"] = 5
        if intent.get("soft", {}).get("fabrics") and items:
            gaps = sum(1 for p, _ in items if not p["fabric"])
            if gaps:
                res["steps"].append(("Catalog gaps", "flag_listing()", f"{gaps} of {len(items)} results don't state a fabric; "
                                     "flagged to the catalog team (fabric was inferred, so they rank below listings that state it)"))
        res.update(items=items, relaxed=relaxed, near=[p["id"] for p in near])
        S.last_results = [p["id"] for p, _ in items]
        S.history.append(f"{q} -> {intent.get('interpretation','')}")
    res["t"] = time.time() - t0
    S.result = res
    S.view = "search"
    record_search(res)


def record_search(res):
    n = len(res.get("items") or [])
    if res["kind"] == "agent":
        it = res.get("intent", {})
        for t in it.get("hard", {}).get("types") or []: note_behaviour("type", t)
        for cf in it.get("soft", {}).get("colour_family") or []: note_behaviour("colour_family", cf, 0.5)
        if it.get("soft", {}).get("occasion"): note_behaviour("occasion", it["soft"]["occasion"])
    elif res["kind"] == "keyword":
        for t, _ in (res.get("kw_filters") or {}).get("types", []): note_behaviour("type", t)
    S.metrics["searches"].append(dict(q=res["query"], kind=res["kind"], t=res["t"], n=n,
                                      stage=res["route"]["stage"] if res["route"]["stage"] != "agent" else res.get("intent", {}).get("stage"),
                                      clarify=bool(res.get("intent", {}).get("stage") == 4 and res.get("intent", {}).get("clarify")),
                                      conf=res.get("intent", {}).get("confidence")))
    items = [(p, checks) for p, checks in res["items"]] if res["kind"] == "agent" else [(PRODUCTS[i], []) for i in res.get("items") or []]
    _search_log().append(dict(
        at=time.time(), sid=S.sid, tag=f"{S.sid}-{S.search_seq}", profile=S.profile.get("name"), q=res["query"], kind=res["kind"],
        stage=S.metrics["searches"][-1]["stage"], t=res["t"], t_ai=res.get("t_ai"), n=n, model=res.get("model"),
        cached=any(l == "served from cache" for l in res.get("ai_log") or []), fallback=bool(res.get("fallback")),
        # the full record behind "View full log" in the admin tab
        route={k: res["route"].get(k) for k in ("label", "reason", "query", "fixes")}, steps=list(res.get("steps") or []),
        ai_log=list(res.get("ai_log") or []), intent=json.loads(json.dumps(res.get("intent") or {}, default=str)),
        relaxed=[f"{k}: {v}" for k, v in res.get("relaxed") or []],
        results=[dict(brand=p["brand"], name=p["name"], type=p["type"], colour=p["colour"], fabric=p["fabric"], price=p["price"],
                      checks=" ".join(("✓ " if ok else "✕ " if ok is False else "? ") + nm for nm, ok, _ in checks))
                 for p, checks in items]))
    A.set_log_tag(None)
    if res["kind"] == "agent" and (res.get("intent", {}).get("soft", {}).get("fabrics")):
        S.metrics["flagged"].update(p["id"] for p, _ in res["items"] if not p["fabric"])   # catalog gap: fabric not stated


def go_tab(t):
    S.tab = S.last_tab = t


def _tab_changed():
    if S.tab is None:  # clicking the selected tab again deselects it; keep the previous one
        S.tab = S.last_tab
    else:
        S.last_tab = S.tab


def open_cart():
    S.view = "cart"; go_tab(TABS[0])


def go_home():
    S.result, S.view, S.home_n = None, "search", 24; go_tab(TABS[0])

# ------------------------------------------------------------------ profiles (several shoppers per account)
def _pick(pred, n, salt):
    """Deterministic demo picks from the real catalog."""
    ids = sorted((pid for pid, p in PRODUCTS.items() if p["source"] == "myntra" and pred(p)), key=lambda i: zlib.crc32(f"{i}|{salt}".encode()))
    return ids[:n]


def _order(pid, size, outcome, when):
    return dict(pid=pid, size=size, outcome=outcome, when=when)


def seed_profiles():
    """Demo order history for the three personas in the solution doc (illustrative, not real orders)."""
    women = lambda t: (lambda p: p["gender"] == "women" and p["type"] == t)
    men = lambda t: (lambda p: p["gender"] == "men" and p["type"] == t)
    pk = lambda pred, salt: (_pick(pred, 1, salt) or [None])[0]
    profs = {
        "Priya": dict(gender="women", usual_size="M", waist=None, anchor_brand=None, anchor_size=None, orders=[
            _order(pk(lambda p: women("kurta set")(p) and p["colour_family"] == "pastel", 1), "M", "kept · fits well", "Aug"),
            _order(pk(lambda p: women("kurta")(p) and p["colour_family"] == "bright", 2), "S", "returned · too small", "Jul"),
            _order(pk(women("dress"), 3), "M", "kept · fits well", "May")]),
        "Ananya": dict(gender="women", usual_size="M", waist=None, anchor_brand=None, anchor_size=None, orders=[
            _order(pk(women("top"), 4), "M", "kept · fits well", "Sep"),
            _order(pk(women("jeans"), 5), "30", "returned · too small at the waist", "Jun"),
            _order(pk(women("kurta"), 6), "M", "kept · fits well", "Mar")]),
        "Rohan": dict(gender="men", usual_size="M", waist=None, anchor_brand=None, anchor_size=None, orders=[
            _order(pk(men("shirt"), 7), "M", "kept · fits well", "Sep"),
            _order(pk(men("t-shirt"), 8), "M", "kept · fits well", "Aug"),
            _order(pk(men("trousers"), 9), "34", "returned · too loose", "Jul")]),
    }
    for name, pr in profs.items():
        pr["orders"] = [o for o in pr["orders"] if o["pid"]]
        pr["past_brands"] = sorted({PRODUCTS[o["pid"]]["brand"] for o in pr["orders"] if o["outcome"].startswith("kept")})
        pr.update(name=name, behaviour={})
    return profs


S.setdefault("profiles", seed_profiles())
S.setdefault("active_profile", "Priya")
if S.active_profile not in S.profiles:
    S.active_profile = next(iter(S.profiles))
S.profile = S.profiles[S.active_profile]


def note_behaviour(kind, value, w=1.0):
    """What this profile searches for and adds, so suggestions follow behaviour, not only past orders."""
    if value:
        b = S.profile.setdefault("behaviour", {})
        b[f"{kind}:{value}"] = b.get(f"{kind}:{value}", 0) + w


def profile_prefs(pr):
    """Weights per attribute from kept orders (strong) and this session's behaviour (lighter)."""
    prefs = {"type": collections.Counter(), "colour_family": collections.Counter(), "brand": collections.Counter(), "occasion": collections.Counter()}
    for o in pr.get("orders", []):
        p = PRODUCTS[o["pid"]]
        w = 2.0 if o["outcome"].startswith("kept") else 0.5   # a return still says what they were shopping for
        prefs["type"][p["type"]] += w; prefs["colour_family"][p["colour_family"]] += w
        if o["outcome"].startswith("kept"): prefs["brand"][p["brand"]] += 1
        for oc in p["occasions"][:2]: prefs["occasion"][oc] += w / 2
    for key, w in pr.get("behaviour", {}).items():
        field, _, v = key.partition(":")
        if field in prefs: prefs[field][v] += w
    return prefs


def set_anchor(brand, size):
    """'This brand in this size fits me' (from a past order, a tag photo or the fit question). It also becomes the usual
    size, so the sidebar never shows two different sizes. Runs as a button callback, before the sidebar widgets exist."""
    pr, k = S.profile, S.profile["name"]
    pr["anchor_brand"] = brand
    if str(size).isdigit():
        pr["waist"] = S[f"wa_{k}"] = str(size)
    else:
        pr["anchor_size"] = pr["usual_size"] = S[f"us_{k}"] = size


def clear_anchor():
    S.profile.update(anchor_brand=None, anchor_size=None)


def use_as_anchor(pid, size):
    """A past order that fitted well becomes the size anchor for the fit agent."""
    p = PRODUCTS[pid]
    set_anchor(p["brand"], size)
    if p["brand"] not in S.profile["past_brands"]: S.profile["past_brands"] = S.profile["past_brands"] + [p["brand"]]
    st.toast(f"Fit anchor set: {p['brand']} {size}")


def shop_similar(pid):
    p = PRODUCTS[pid]
    q = f"{p['colour'].split(' & ')[0]} {p['type']}"
    S.q = q; run_search(q); go_tab(TABS[0])


# ------------------------------------------------------------------ sidebar
OTHER_BRAND = "Other (type it)"


def _create_profile():
    name = (S.get("new_profile_name") or "").strip()
    if name and name not in S.profiles:
        S.profiles[name] = dict(name=name, gender=S.get("new_profile_gender", "women"), usual_size=None, waist=None,
                                anchor_brand=None, anchor_size=None, past_brands=[], orders=[], behaviour={})
        S.active_profile = name


@st.cache_data(show_spinner=False)
def cached_read_image(digest, data, mime, _key, models):
    return A.read_image(data, mime, _key, list(models))


with st.sidebar:
    st.markdown("### 👤 Shopping for")
    names = list(S.profiles)
    st.selectbox("Profile", names, key="active_profile", label_visibility="collapsed",
                 help="Each profile keeps its own sizes, past orders and suggestions (e.g. you, a parent, a partner).")
    S.profile = pr = S.profiles[S.active_profile]
    with st.popover("➕ New profile", use_container_width=True):
        st.text_input("Name", key="new_profile_name", placeholder="e.g. Mom, Rahul")
        st.radio("Shops for", ["women", "men"], key="new_profile_gender", horizontal=True)
        st.button("Create profile", on_click=_create_profile, type="primary")

    st.markdown("#### Fit profile")
    st.caption("Used to recommend a size on every product, whichever way you search. Only this session, this profile's orders "
               "and what you choose to share are used; nothing is stored.")
    k = pr["name"]   # widget keys per profile, so switching profiles shows that person's values
    # a default only on first show: set_anchor() may already have put a value in session state, and Streamlit warns on both
    first = lambda key, i: {} if key in S else dict(index=i)
    us = st.selectbox("Usual top size", ["Not set"] + SIZE_ORDER, key=f"us_{k}",
                      **first(f"us_{k}", (SIZE_ORDER.index(pr["usual_size"]) + 1) if pr.get("usual_size") in SIZE_ORDER else 0))
    wa = st.selectbox("Usual waist (jeans)", ["Not set"] + WAIST_ORDER, key=f"wa_{k}",
                      **first(f"wa_{k}", (WAIST_ORDER.index(pr["waist"]) + 1) if pr.get("waist") in WAIST_ORDER else 0))
    brands = [b for b in ANCHOR_BRANDS if b != "None / not sure"]
    cur = pr.get("anchor_brand")
    opts = ["None / not sure"] + brands + [OTHER_BRAND]
    ab = st.selectbox("Brand that fits you best", opts, key=f"ab_{k}_{cur}",
                      index=opts.index(cur) if cur in opts else (opts.index(OTHER_BRAND) if cur else 0))
    if ab == OTHER_BRAND:
        typed = st.text_input("Type the brand", value=cur if cur not in opts else "", key=f"abt_{k}", placeholder="e.g. Uniqlo, Libas")
        ab = typed.strip() or None
    if ab and ab != "None / not sure":
        cur_sz = pr.get("anchor_size") or pr.get("usual_size")
        asz = st.selectbox(f"Your top size in {ab}", ["Not set"] + SIZE_ORDER, key=f"as_{k}_{ab}_{pr.get('anchor_size')}",
                           index=(SIZE_ORDER.index(cur_sz) + 1) if cur_sz in SIZE_ORDER else 0)
        pr["anchor_size"] = None if asz == "Not set" else asz
        used = [f"tops: **{ab} {pr['anchor_size']}**" + (f" (instead of your usual {us})" if us not in ("Not set", pr["anchor_size"]) else "")
                if pr["anchor_size"] else None,
                f"jeans: **waist {wa}**" if wa != "Not set" else None]
        used = [u for u in used if u]
        if used:
            st.caption("Size badges use " + "; ".join(used) + ".")
        st.button("✕ Stop using this brand", key=f"clr_{k}", on_click=clear_anchor, use_container_width=True)
    gd = st.radio("Shops for", ["Women", "Men", "Any"], horizontal=True, key=f"gd_{k}",
                  index={"women": 0, "men": 1}.get(pr.get("gender"), 2))
    pb = st.multiselect("Brands bought here", sorted({p["brand"] for p in PRODUCTS.values()}), default=pr.get("past_brands", []), key=f"pb_{k}")
    pr.update(usual_size=None if us == "Not set" else us, waist=None if wa == "Not set" else wa,
              anchor_brand=None if ab in (None, "None / not sure") else ab, past_brands=pb,
              anchor_size=pr.get("anchor_size") if ab not in (None, "None / not sure") else None,
              gender=None if gd == "Any" else gd.lower())

    # past orders: browse and pick one as the size anchor, or shop something similar
    with st.expander(f"🧾 Past orders ({len(pr.get('orders', []))})"):
        if not pr.get("orders"):
            st.caption("No orders yet for this profile.")
        for j, o in enumerate(pr.get("orders", [])):
            p = PRODUCTS[o["pid"]]
            st.markdown(f"<div class='pbrand'>{html.escape(p['brand'])}</div><div class='why' style='min-height:0'>{html.escape(p['name'][:60])}"
                        f"<br>Size {o['size']} · {html.escape(o['outcome'])} · {o['when']}</div>", unsafe_allow_html=True)
            o1, o2 = st.columns(2)
            if o["outcome"].startswith("kept"):
                o1.button("Fits me: use size", key=f"anc{k}{j}", on_click=use_as_anchor, args=(o["pid"], o["size"]), use_container_width=True)
            o2.button("Shop similar", key=f"sim{k}{j}", on_click=shop_similar, args=(o["pid"],), use_container_width=True)
        st.caption("Demo order history (illustrative).")

    # photo of a size tag, bill or label -> brand + size + product, read by Gemini vision
    with st.expander("📷 Read a size tag, bill or label"):
        up = st.file_uploader("Photo", type=["png", "jpg", "jpeg", "webp"], key=f"up_{k}", label_visibility="collapsed")
        if up is not None:
            data = up.getvalue()
            st.image(data, use_container_width=True)
            d, model, log = cached_read_image(hashlib.md5(data).hexdigest(), data, up.type or "image/jpeg", API_KEY, tuple(MODELS))
            if not d:
                st.info("Reading photos needs AI mode (a Gemini key)." if not API_KEY else "Couldn't read that photo: " + "; ".join(log)[:160])
            else:
                st.markdown(f"**I read:** {html.escape(d.get('summary') or d.get('kind') or '')}")
                facts = [f"{k2}: {d[k2]}" for k2 in ("brand", "product_type", "size", "waist", "colour", "price") if d.get(k2)]
                if facts: st.caption(" · ".join(facts))
                size = d.get("size") or d.get("waist")
                c1, c2 = st.columns(2)
                if d.get("brand") and size:
                    c1.button("Use as my size", key=f"tag_anchor_{k}", use_container_width=True, on_click=set_anchor,
                              args=(d["brand"], size), help=f"Sets {d['brand']} {size} as the size that fits you, and your usual size to {size}")
                q = " ".join(x for x in (d.get("colour"), d.get("product_type")) if x)
                if q and c2.button("Search this", key=f"tag_search_{k}", use_container_width=True):
                    S.q = q; run_search(q); go_tab(TABS[0]); st.rerun()

    st.divider()
    show_trace = st.toggle("Show agent trace", value=True, help="Shows the trace under each search result. The 🧠 AI trace tab always has the full trace.")
    st.markdown(f"**AI model:** {'Gemini (' + MODELS[0] + ')' if API_KEY else 'offline rules (no key set)'}")
    st.caption(f"Catalog: {CATALOG_SOURCE}. Titles, brands, prices and images are real Myntra listings; colour, fabric, occasion "
               "and style are inferred from the text, and sizes and fit signals are simulated for this demo.")
    st.divider()
    st.button(f"🛒 Cart ({len(S.cart)})", use_container_width=True, key="cart_side", on_click=open_cart)

# ------------------------------------------------------------------ top bar: logo + search, then tabs
with st.form("search", clear_on_submit=False, border=False):
    c0, c1, c2 = st.columns([1.5, 7, 1.1], vertical_alignment="center")
    c0.markdown('<div class="ss-logo">Search<b>Sense</b></div>', unsafe_allow_html=True)
    q = c1.text_input("Search", placeholder="Search, or describe what you need… e.g. 'breathable pastel outfit for a daytime wedding under ₹6,000'",
                      label_visibility="collapsed", key="q")
    go = c2.form_submit_button("Search", use_container_width=True, type="primary")
if go and q.strip():
    run_search(q.strip())
    go_tab(TABS[0])

n1, n2, n3, n4 = st.columns([5.6, 1.2, 1.1, 0.75], vertical_alignment="center")
with n1:
    st.segmented_control("Section", TABS, key="tab", on_change=_tab_changed, label_visibility="collapsed")
n2.button("🏠 All products", use_container_width=True, key="home_top", on_click=go_home)
n3.button(f"🛒 Cart ({len(S.cart)})", use_container_width=True, key="cart_top", on_click=open_cart)
def _toggle_theme():
    S.dark_mode = not S.dark_mode
    if S.dark_mode: st.query_params["theme"] = "dark"
    else: st.query_params.pop("theme", None)


n4.button("☀️ Light" if S.dark_mode else "🌙 Dark", use_container_width=True, key="theme_top",
          help="Switch between light and dark mode", on_click=_toggle_theme)

# ------------------------------------------------------------------ test cases (scripted personas)
# the case brief's own example, word for word: the first thing to show (Myntra's search returns "No results" for it)
PROBLEM_QUERY = ("I need a breathable, pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 "
                 "that pairs well with silver jewelry")

TEST_CASES = [
    dict(name="Case brief", icon="📄", tag="Stage 3 · the problem statement", query=PROBLEM_QUERY, profile="Priya",
         tests="The exact query from the case brief: many constraints, subjective words, weather and occasion.",
         expect="Breathable pastel ethnic outfits under ₹6,000 that suit silver jewellery, with Mumbai's humid weather and the "
                "day-wedding rules in the trace, and a size on every card."),
    dict(name="Rohan", icon="⌨️", tag="Stage 2 · typo", query="wite linnen shirt M", profile="Rohan",
         tests="Spelling correction and a size in a short query.",
         expect="“wite linnen” is fixed to “white linen” without asking; shirts stocked in M; fit badge on every card."),
    dict(name="Priya", icon="🌸", tag="Stage 3 · complex intent", profile="Priya",
         query="breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery",
         tests="Subjective words mapped to attributes, plus the AI's weather estimate and the occasion rules.",
         expect="Breathable pastel ethnic sets under ₹6,000; the trace shows the Mumbai weather (AI estimate) and day-wedding rules."),
    dict(name="Ananya", icon="👖", tag="Stage 1 · fit", query="high-waist straight jeans for office", profile="Ananya",
         tests="Fit agent when there is no size history.",
         expect="Ananya returned jeans in 30 for being too small, so the fit agent starts from 32 and adjusts for each pair "
                "(“34 recommended · runs small”, medium confidence), offering one question to confirm. Switch to a new profile "
                "to see the no-history case: “Not sure of your size”, the question and the size chart, never a guess. "
                "Add two sizes to see the cart's ‘Keep only’ fix."),
    dict(name="Ambiguous", icon="❓", tag="Stage 4 · clarify", query="outfit for a wedding",
         tests="Asking one question only when the answer splits results.",
         expect="One question: Ethnic, Western or Show both. Tapping an option re-runs the search."),
    dict(name="No exact match", icon="⚖️", tag="Stage 5 · relax", query="chanderi lehenga for a day wedding under ₹6,000",
         tests="Verifier loop relaxing a soft constraint.",
         expect="No chanderi lehenga under ₹6,000, so fabric is relaxed while the budget is kept, and the app says so."),
    dict(name="Lifestyle", icon="💡", tag="Non-fashion", query="minimal table lamp for a small reading corner, warm light, under 2500",
         tests="Same agent on a home product.",
         expect="A small warm-light lamp under ₹2,500; no size check because it is not clothing."),
    dict(name="Skincare", icon="🧴", tag="Personal care",
         query="fragrance-free moisturiser for oily acne-prone skin that sits well under sunscreen under 800",
         tests="Needs-based constraints checked against product notes.",
         expect="Only the oil-free, fragrance-free gel moisturiser passes every check."),
    dict(name="Order help", icon="📦", tag="Stage 6 · out of scope", query="where is my order",
         tests="Router spotting a non-search question.",
         expect="“This isn’t a search query”: no product search, redirected to Customer Care / help chat. "
                "Try “Return order” or “refund not received” too."),
    dict(name="Follow-up", icon="🔁", tag="Memory · refine", query="#2 but cheaper", profile="Priya",
         setup="breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery",
         tests="Refining the previous search by pointing at a result.",
         expect="Runs Priya's search, then “#2 but cheaper”: the budget drops below result #2's price and the style is kept."),
]


def run_case(case):
    S.history, S.last_results = [], []   # each test case starts a fresh session
    if case.get("profile") in S.profiles:   # Rohan, Priya and Ananya shop as their own profile
        S.active_profile = case["profile"]; S.profile = S.profiles[case["profile"]]
    if case.get("setup"):
        run_search(case["setup"])
        run_search(case["query"], followup=True)
    else:
        run_search(case["query"])
    S.q = case["query"]
    go_tab(TABS[0])


def view_tests():
    st.markdown(f'<div class="tc-intro"><b>Test cases</b> · {len(TEST_CASES)} scripted shoppers that exercise each part of the pipeline. '
                'Run one to see the results in 🏠 Shop; the 🧠 AI trace tab then shows every step the agent took.</div>', unsafe_allow_html=True)
    for r0 in range(0, len(TEST_CASES), 3):
        cols = st.columns(3)
        for c, case in zip(cols, TEST_CASES[r0:r0 + 3]):
            with c, st.container(border=True):
                pre = f'<div class="tc-q">1. “{html.escape(case["setup"][:60])}…”<br>2. “{html.escape(case["query"])}”</div>' if case.get("setup") \
                    else f'<div class="tc-q">“{html.escape(case["query"])}”</div>'
                st.markdown(f'<span class="tcm"></span><div class="tc-head"><span class="tc-ic">{case["icon"]}</span>'
                            f'<div><div class="tc-name">{html.escape(case["name"])}</div><span class="tc-tag">{html.escape(case["tag"])}</span></div></div>'
                            f'{pre}<div class="tc-l">Tests</div><div class="tc-t">{html.escape(case["tests"])}</div>'
                            f'<div class="tc-l">Expected</div><div class="tc-t">{html.escape(case["expect"])}</div>', unsafe_allow_html=True)
                st.button("Run test", key="tc" + case["name"], use_container_width=True, type="primary", on_click=run_case, args=(case,))

# ------------------------------------------------------------------ tutorial (guided tour for first-time users)
TUTORIAL = [
    dict(icon="👤", title="Pick who is shopping", profile="Priya", home=True, button="Shop as Priya",
         do="Choose a shopper from the Profile menu in the left sidebar. Priya, Ananya and Rohan come with past orders; "
            "➕ New profile adds your own.",
         look="The home page opens with “Picked for Priya”, based on her orders and what she browses. A men's profile only sees men's fashion."),
    dict(icon="💬", title="Search in your own words", profile="Priya", query="breathable pastel kurta for haldi under 2500",
         do="Describe what you need the way you'd say it to a friend: occasion, colour, budget, fabric.",
         look="The reasoning bubble (You typed / I understood / So I'm showing), the Gender · Item · Colour chips "
              "(tap one to remove it), and the Best match ribbon on the top result."),
    dict(icon="✏️", title="Don't worry about typos", query="Vlue kurta",
         do="Type quickly, spelling mistakes and all. Short forms like “sari” or “tshirt” work too.",
         look="It searches for blue kurta and tells you. Tap “Search instead for …” to use your exact words."),
    dict(icon="❓", title="Answer one quick question", query="outfit for a wedding",
         do="Try something vague, where the answer could go two very different ways.",
         look="One question with tap-to-answer options (Ethnic, Western or Show both). Tap one and the results update."),
    dict(icon="🔁", title="Keep the conversation going", profile="Priya", setup="breathable pastel kurta for haldi under 2500",
         query="#2 but cheaper",
         do="Refine your results with the follow-up bar under them: “in blue”, “less heavy”, “#2 but cheaper”.",
         look="The app keeps what you already asked for and changes only what you said, here a lower budget than result #2."),
    dict(icon="📏", title="Find your size", profile="Ananya", query="high-waist straight jeans for office",
         do="Search for clothes as Ananya. She once returned jeans in 30 for being too small.",
         look="A size badge on every card: “Take M” (sure), “34 recommended · runs small” (fairly sure, with the reason), "
              "or “Not sure of your size” (no guess: check the size chart)."),
    dict(icon="🛍️", title="Explore a product", profile="Ananya", query="high-waist straight jeans for office", open_top=True,
         button="Open a product",
         do="Open any product to see the full picture before you buy.",
         look="Why this size, “Ask about this product” (preview) and “Complete the look”. Add two sizes to the cart to see the checkout size check."),
    dict(icon="📦", title="Ask for help, not products", query="Return order",
         do="Type an order or refund question into the same search bar.",
         look="“This isn't a search query”: no products, just a hand-off to Customer Care or help chat."),
    dict(icon="⚙️", title="Make it yours", home=True, button="Go to the home page",
         do="In the sidebar: set your usual size and brand (type it in if it's not listed), upload a photo of a size tag or bill, "
            "and open Past orders to “Shop similar”. 🌙 Dark in the top bar switches the theme.",
         look="Size badges and “Picked for you” update as soon as your profile changes."),
    dict(icon="🧠", title="See behind the scenes", tab=3, button="Open the AI trace",
         do="After any search, open 🧠 AI trace to see every step the AI took. 📊 Metrics shows the success measures, "
            "and 🧪 Test cases runs ten ready-made shoppers.",
         look="How the request was understood, which checks ran, and what was relaxed when nothing matched exactly."),
]
S.setdefault("tut_done", set())


def run_tutorial(i):
    step = TUTORIAL[i]
    S.tut_done.add(i)
    if step.get("profile") in S.profiles:
        S.active_profile = step["profile"]; S.profile = S.profiles[step["profile"]]
    if step.get("tab"):
        go_tab(TABS[step["tab"]]); return
    if step.get("home"):
        go_home(); return
    S.history, S.last_results = [], []   # each step starts a fresh conversation
    if step.get("setup"):
        run_search(step["setup"])
        run_search(step["query"], followup=True)
    else:
        run_search(step["query"])
    S.q = step["query"]
    if step.get("open_top") and S.last_results:
        S.pid, S.view = S.last_results[0], "product"
    go_tab(TABS[0])


def view_tutorial():
    done = len(S.tut_done)
    st.markdown('<div class="tc-intro"><b>Tutorial</b> · a 2-minute tour of SearchSense. Each step tells you what to try and what to look for; '
                '<b>▶ Try it</b> runs it for you in 🏠 Shop. Come back here for the next step.</div>', unsafe_allow_html=True)
    st.progress(done / len(TUTORIAL), text=f"{done} of {len(TUTORIAL)} steps tried" + (" · you've seen it all 🎉" if done == len(TUTORIAL) else ""))
    for r0 in range(0, len(TUTORIAL), 2):
        cols = st.columns(2)
        for c, (i, step) in zip(cols, list(enumerate(TUTORIAL))[r0:r0 + 2]):
            with c, st.container(border=True):
                q = f'<div class="tc-q">“{html.escape(step["query"])}”</div>' if step.get("query") else ""
                if step.get("setup"):
                    q = f'<div class="tc-q">1. “{html.escape(step["setup"])}”<br>2. “{html.escape(step["query"])}”</div>'
                tick = '<span class="tut-done">✓ Tried</span>' if i in S.tut_done else ""
                st.markdown(f'<span class="tcm"></span><div class="tc-head"><span class="tc-ic">{step["icon"]}</span>'
                            f'<div><span class="tc-tag">Step {i + 1}</span>{tick}<div class="tc-name">{html.escape(step["title"])}</div></div></div>'
                            f'<div class="tc-l">Do this</div><div class="tc-t">{html.escape(step["do"])}</div>{q}'
                            f'<div class="tc-l">Look for</div><div class="tc-t">{html.escape(step["look"])}</div>', unsafe_allow_html=True)
                st.button("▶ " + step.get("button", "Try it"), key=f"tut{i}", use_container_width=True,
                          type="secondary" if i in S.tut_done else "primary", on_click=run_tutorial, args=(i,))

# ------------------------------------------------------------------ metrics (solution doc: impact, KPIs)
def view_metrics():
    m = S.metrics
    ss = m["searches"]
    st.markdown('<div class="tc-intro"><b>Session metrics</b> · the KPIs from the solution doc, measured live for this browser session. '
                'In the pilot they come from an A/B test: a share of search traffic on AI mode, the rest on current search.</div>',
                unsafe_allow_html=True)
    if not ss:
        st.info("Run a few searches or test cases, add something to the cart, and come back."); return
    product = [x for x in ss if x["kind"] != "help"]
    ai = [x for x in product if x["kind"] == "agent"]
    kw = [x for x in product if x["kind"] == "keyword"]
    zero = [x for x in product if x["n"] == 0]
    clar = [x for x in ai if x["clarify"]]
    rec_adds = [a for a in m["adds"] if a["rec"]]
    accepted = [a for a in rec_adds if a["size"] == a["rec"]]
    pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "–"
    ms = lambda xs: f"{1000 * sorted(xs)[len(xs) // 2]:.0f} ms" if xs else "–"
    rows = [
        ("Search-to-checkout conversion", "North star", "+20% vs keyword search",
         f"{m['orders']} order(s) from {len(product)} searches ({pct(m['orders'], len(product))})"),
        ("Size- and style-related return rate", "North star", "−15%",
         f"measured after delivery; proxy here: {m['nudges_accepted']} of {m['nudges_shown']} return-risk nudges accepted"),
        ("Zero-result and low-result searches", "Supporting", "Down", f"{len(zero)} of {len(product)} ({pct(len(zero), len(product))})"),
        ("AI-mode queries that needed a clarifying question", "Guardrail", "Kept low", f"{len(clar)} of {len(ai)} ({pct(len(clar), len(ai))})"),
        ("Accepted size recommendation rate", "Supporting", "Up", f"{len(accepted)} of {len(rec_adds)} adds kept our size ({pct(len(accepted), len(rec_adds))})"),
        ("Search latency, pass-through queries", "Guardrail", "No change vs today", f"median {ms([x['t'] for x in kw])} (AI mode: {ms([x['t'] for x in ai])})"),
    ]
    st.dataframe([{"KPI": a, "Type": b, "Target": c, "This session": d} for a, b, c, d in rows], hide_index=True, use_container_width=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Searches", len(ss)); c2.metric("Sent to AI mode", pct(len(ai), len(product)))
    c3.metric("Support hand-offs", sum(1 for x in ss if x["kind"] == "help")); c4.metric("Listings flagged to catalog team", len(m["flagged"]))
    st.markdown('<div class="layer">Searches by stage</div>', unsafe_allow_html=True)
    by = collections.Counter(STAGE_PILL.get(x["stage"], (str(x["stage"]),))[0] for x in ss)
    st.dataframe([{"Stage": k, "Searches": v} for k, v in sorted(by.items())], hide_index=True, use_container_width=True)
    with st.expander("Search log"):
        st.dataframe([{"Query": x["q"], "Path": x["kind"], "Stage": x["stage"], "Results": x["n"], "Seconds": round(x["t"], 2),
                       "Agent confidence": x["conf"] or ""} for x in reversed(ss)], hide_index=True, use_container_width=True)


# ------------------------------------------------------------------ admin (what happens in the background)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
_clock = lambda ts: datetime.datetime.fromtimestamp(ts, IST).strftime("%H:%M:%S")


def _admin_login():
    with st.columns([1, 1.4])[0], st.form("admin_login", border=True):
        st.markdown("**🔐 Admin sign-in** · see what the app is doing behind the scenes")
        u = st.text_input("ID")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", type="primary"):
            ok_u = hmac.compare_digest(u, str(_secret("ADMIN_USER", "admin")))
            ok_p = hmac.compare_digest(p, str(_secret("ADMIN_PASSWORD", "admin")))
            if ok_u and ok_p:
                S.admin_ok = True; st.rerun()
            st.error("Wrong ID or password.")


def _pretty(txt):
    """Gemini's reply as indented JSON when it is JSON, else as sent."""
    try:
        return json.dumps(json.loads(txt), indent=2, ensure_ascii=False), "json"
    except Exception:
        return txt or "", "text"


def _show_call(c, n=None):
    head = f"{'Call ' + str(n) + ' · ' if n else ''}{_clock(c['at'])} · {c['purpose']} · **{c['model']}** · " \
           + ("✅ OK" if c["status"] == 200 else f"❌ {c['status']}") + f" · {c['secs']}s"
    st.markdown(head)
    if c.get("prompt_tokens") is not None:
        st.caption(f"Tokens: prompt {c.get('prompt_tokens')} (cached {c.get('cached_tokens') or 0}) · thinking "
                   f"{c.get('thinking_tokens') or 0} · reply {c.get('output_tokens')}")
    sent = c.get("request", "")
    extras = [x for x, on in (("the system prompt (master prompt)", c.get("system_prompt")),
                              ("the strict JSON response schema", c.get("schema"))) if on]
    st.markdown("**Sent to Gemini**" + (f" · together with {' and '.join(extras)}" if extras else ""))
    st.code(sent or "(nothing recorded)", language="text", wrap_lines=True)
    st.markdown("**Gemini replied**" if c["status"] == 200 else "**Error from Google**")
    body, lang = _pretty(c.get("reply", ""))
    st.code(body or "(empty)", language=lang, wrap_lines=True)


@st.dialog("Full log of this search", width="large")
def _search_detail(x):
    st.markdown(f"### “{html.escape(x['q'])}”")
    path = {"agent": "AI", "keyword": "normal search", "help": "customer care"}.get(x["kind"], x["kind"])
    st.caption(f"{_clock(x['at'])} IST · visitor {x['sid']} · profile {x['profile']} · path {path}"
               + (" (safety net)" if x["fallback"] else "") + f" · stage {x['stage']} · {x['n']} results")
    c = st.columns(3)
    c[0].metric("Total", f"{x['t']:.2f}s"); c[1].metric("Waiting for AI", f"{x['t_ai'] or 0:.2f}s")
    c[2].metric("App work", f"{x['t'] - (x['t_ai'] or 0):.2f}s")

    st.markdown("#### 1 · Router")
    r = x.get("route") or {}
    st.markdown(f"**{html.escape(str(r.get('label')))}** · {html.escape(str(r.get('reason')))}"
                + (f"  \nSpelling fixes: {', '.join(f'{a} → {b}' for a, b in r['fixes'])}" if r.get("fixes") else ""))

    st.markdown("#### 2 · Gemini")
    calls = [cl for cl in A.CALL_LOG if cl.get("tag") == x.get("tag")]
    if x["cached"]:
        st.info("Served from cache: the same search was answered before, so Gemini was not called. The answer below is the saved one.")
    elif not calls and x["kind"] == "keyword" and not x["fallback"]:
        st.info("No AI call: a short, specific query goes straight to normal search.")
    elif not calls and x["kind"] == "help" and not x.get("intent"):
        st.info("No AI call: the router recognised an order or returns question and sent it straight to Customer Care.")
    elif not calls:
        st.info("No Gemini call recorded" + ("" if API_KEY else " (no GEMINI_API_KEY: offline rules were used)") + ".")
    for i, cl in enumerate(calls, 1):
        with st.container(border=True):
            _show_call(cl, i)
    if x.get("ai_log"):
        st.caption("Agent log: " + " · ".join(x["ai_log"]))

    if x.get("intent"):
        st.markdown("#### 3 · What the AI understood (after the validator)")
        st.json(x["intent"], expanded=True)

    st.markdown("#### 4 · Every step")
    for i, (a, b, o) in enumerate(x.get("steps") or [], 1):   # full text, wrapped: outputs can be long (e.g. Google errors)
        st.markdown(f"{i}. **{html.escape(str(a))}** · `{html.escape(str(b))}`  \n{html.escape(str(o))}")
    if x.get("relaxed"):
        st.markdown("Relaxed to find results: " + ", ".join(x["relaxed"]))

    st.markdown(f"#### 5 · Results shown ({len(x.get('results') or [])})")
    if x.get("results"):
        st.dataframe([{"#": i + 1, "Brand": p["brand"], "Product": p["name"], "Type": p["type"], "Colour": p["colour"],
                       "Fabric": p["fabric"], "₹": p["price"], "Checks": p["checks"]} for i, p in enumerate(x["results"])],
                     hide_index=True, use_container_width=True)
    elif x["kind"] == "help":
        st.markdown("No products: the shopper was sent to Customer Care. Reply: "
                    + html.escape(str((x.get("intent") or {}).get("reply") or "redirect to help chat")))
    st.download_button("⬇️ Download this log (JSON)", json.dumps(dict(x, gemini_calls=calls), indent=2, ensure_ascii=False, default=str),
                       file_name=f"searchsense-log-{x.get('tag')}.json", mime="application/json")


@st.dialog("Gemini call", width="large")
def _call_detail(c):
    _show_call(c)
    if c.get("system_prompt"):
        with st.expander("System prompt (master prompt) sent with this call"):
            st.code(A.SYSTEM, language="text", wrap_lines=True)


# ------------------------------------------------------------------ demo pre-run (admin): answers ready before the jury watches
# Each entry: (query, profile, extras). Extras: "chips" = also run its one-tap follow-ups, "qa" = the 4 preset product
# questions on the top 2 results, "clarify" = each clarifying option, "follow" = typed follow-ups.
PRERUN_PLAN = [
    (PROBLEM_QUERY, "Priya", dict(chips=True, qa=True, follow=["#2 but cheaper", "same but in blue"])),
    ("breathable pastel kurta for haldi under 2500", "Priya", dict(chips=True, qa=True, follow=["#2 but cheaper"])),
    ("high-waist straight jeans for office", "Ananya", dict(chips=True, qa=True)),
    ("I want clothes for my Jaipur trip in January", "Priya", dict(chips=True)),
    ("Clothes for Manali", "Priya", dict(chips=True)),
    ("tshirts for manali", "Rohan", dict(chips=True)),
    ("outfit for a wedding", "Priya", dict(clarify=True)),
    ("Vlue kurta", "Priya", {}), ("dress for club", "Priya", {}), ("Tshirt for gym and running", "Rohan", {}),
    ("Return order", "Priya", {}),
]


def _prerun_plan():
    """The demo plan plus every test case, tutorial step and popular search, without duplicates."""
    plan, seen = list(PRERUN_PLAN), {q for q, _, _ in PRERUN_PLAN}
    for c in TEST_CASES:
        if c["query"] not in seen:
            plan.append((c["query"], c.get("profile") or "Priya", dict(setup=c.get("setup")))); seen.add(c["query"])
    for t in TUTORIAL:
        if t.get("query") and t["query"] not in seen:
            plan.append((t["query"], t.get("profile") or "Priya", dict(setup=t.get("setup")))); seen.add(t["query"])
    for q in SUGGESTIONS:
        if q not in seen:
            plan.append((q, "Priya", {})); seen.add(q)
    return plan


def _save_prerun():
    data = {"saved": datetime.datetime.now(IST).isoformat(timespec="minutes"), "models": MODELS,
            "intents": [[q, list(h), prev, list(v)] for (q, h, prev), v in _intent_cache().items()],
            "qa": [[pid, q, list(v)] for (pid, q), v in _qa_cache().items()]}
    txt = json.dumps(data, ensure_ascii=False, default=str)
    try:
        with open(PRERUN_FILE, "w", encoding="utf-8") as f:
            f.write(txt)
    except OSError:
        pass   # read-only disk: the download button still has it
    return txt


def _run_prerun():
    """Run every demo search, follow-up and product question once, pacing calls for the free tier's per-minute limit."""
    import copy
    keep = {k: copy.deepcopy(S[k]) for k in ("result", "history", "last_results", "view", "metrics", "profiles", "qa") if k in S}
    keep_profile = S.active_profile
    plan, rows = _prerun_plan(), []
    bar = st.progress(0.0, text="Starting…")

    def one(q, profile, followup=False):
        S.profile = S.profiles[profile]
        n0, t0 = len(A.CALL_LOG), time.time()
        run_search(q, followup=followup)
        res = S.result
        called = len(A.CALL_LOG) > n0
        rows.append({"Query": q, "Profile": profile, "Path": res["kind"], "Model": res.get("model") or "",
                     "AI call": "yes" if called else "saved / not needed", "Seconds": round(time.time() - t0, 1),
                     "OK": "✅" if res.get("model") != "failed" and not res.get("fallback") else "❌ (safety net)"})
        if called:
            time.sleep(4.5)   # free tier: about 15 calls a minute
        return res

    def products(res):
        return [p for p, _ in res["items"]] if res["kind"] == "agent" else [PRODUCTS[i] for i in res.get("items") or []]

    for n, (q, profile, ex) in enumerate(plan):
        bar.progress(n / len(plan), text=f"{n + 1}/{len(plan)} · {q[:70]}")
        S.history, S.last_results, S.result = [], [], None   # each scenario starts fresh, like the Test cases
        if ex.get("setup"):
            one(ex["setup"], profile)
            one(q, profile, followup=True)
            continue
        res = one(q, profile)
        base = {k: copy.deepcopy(S[k]) for k in ("result", "history", "last_results")}
        follow = list(ex.get("follow", []))
        if ex.get("chips"):
            follow += _quick_refines(res, products(res))
        for f in follow:
            for k, v in base.items(): S[k] = copy.deepcopy(v)
            one(f, profile, followup=True)
        cl = (res.get("intent") or {}).get("clarify")
        if ex.get("clarify") and cl:
            for o in cl["options"]:
                for k, v in base.items(): S[k] = copy.deepcopy(v)
                one(f"{res['query']} — {o}", profile)
        if ex.get("qa") and API_KEY:
            for p in products(res)[:2]:
                for pq in PRODUCT_QUESTIONS:
                    n0 = len(A.CALL_LOG)
                    cached_ask(p, pq)
                    if len(A.CALL_LOG) > n0:
                        time.sleep(4.5)
                rows.append({"Query": f"Ask about “{p['name'][:40]}”", "Profile": profile, "Path": "product questions",
                             "Model": "", "AI call": f"{len(PRODUCT_QUESTIONS)} questions", "Seconds": None, "OK": "✅"})
    bar.progress(1.0, text="Done")
    for k, v in keep.items(): S[k] = v
    S.profile = S.profiles[keep_profile]
    S.prerun_rows = rows
    S.prerun_json = _save_prerun()


def _prerun_panel():
    st.markdown('<div class="layer">⚡ Demo pre-run · make the demo searches instant</div>', unsafe_allow_html=True)
    plan = _prerun_plan()
    st.caption(f"Runs {len(plan)} demo searches once (the case-brief query, must-show scenarios, every test case, tutorial step "
               "and popular search), plus their one-tap follow-ups, clarifying options and the preset product questions, and "
               f"saves the AI's answers. Searches typed with the same words are then instant on stage. Saved answers now: "
               f"{len(_intent_cache())} searches, {len(_qa_cache())} product answers. Takes about 5–10 minutes on the free tier "
               "(calls are paced to its per-minute limit). Tip: put the model that answers fastest first in GEMINI_MODELS.")
    c1, c2, _ = st.columns([1.4, 1.6, 3])
    go = c1.button("⚡ Pre-run demo", type="primary", use_container_width=True, disabled=not API_KEY,
                   help=None if API_KEY else "Needs GEMINI_API_KEY")
    c2.download_button("⬇️ Download saved answers", S.get("prerun_json") or _save_prerun(), file_name="demo_cache.json",
                       mime="application/json", use_container_width=True,
                       help="Commit this file as data/demo_cache.json so the answers load on every restart")
    if go:
        _run_prerun()
        st.success("Pre-run finished. Download the saved answers and send them over to commit, so they survive a restart.")
    if S.get("prerun_rows"):
        st.dataframe(S.prerun_rows, hide_index=True, use_container_width=True)


def _admin_clear():
    A.CALL_LOG.clear(); _search_log().clear()


def view_admin():
    if not S.get("admin_ok"):
        _admin_login(); return
    calls, searches = list(A.CALL_LOG), list(_search_log())
    st.markdown('<div class="tc-intro"><b>Admin</b> · live view of the background work for <b>all visitors</b> since the app last '
                'started (times in IST). Logs are kept in memory and reset when Streamlit restarts.</div>', unsafe_allow_html=True)
    b1, b2, b3, _ = st.columns([1, 1, 1, 4])
    b1.button("🔄 Refresh", use_container_width=True)
    b2.button("🧹 Clear logs", use_container_width=True, on_click=_admin_clear)
    if b3.button("Sign out", use_container_width=True):
        S.admin_ok = False; st.rerun()

    up = time.time() - _started()
    recent = {x["sid"] for x in searches if time.time() - x["at"] < 1800}
    ok = sum(1 for c in calls if c["status"] == 200)
    m = st.columns(5)
    m[0].metric("AI key", "Set" if API_KEY else "Not set")
    m[1].metric("Up for", f"{int(up // 3600)}h {int(up % 3600 // 60)}m")
    m[2].metric("Searches", len(searches))
    m[3].metric("Active visitors (30 min)", len(recent))
    m[4].metric("Gemini calls ok / failed", f"{ok} / {len(calls) - ok}")

    st.markdown('<div class="layer">Models · tried in this order for every AI search</div>', unsafe_allow_html=True)
    rows = []
    for i, mdl in enumerate(MODELS):
        mc = [c for c in calls if c["model"] == mdl]
        good = [c for c in mc if c["status"] == 200]
        bad = [c for c in mc if c["status"] != 200]
        secs = sorted(c["secs"] for c in good)
        think = [c["thinking_tokens"] for c in good if c.get("thinking_tokens")]
        rows.append({"#": i + 1, "Model": mdl, "Calls": len(mc), "OK": len(good), "Failed": len(bad),
                     "Quota refusals (429)": sum(1 for c in bad if c["status"] == 429),
                     "Median time (s)": secs[len(secs) // 2] if secs else None,
                     "Avg thinking tokens": round(sum(think) / len(think)) if think else None,
                     "Last error": (f"{_clock(bad[-1]['at'])} · {bad[-1]['status']}: {bad[-1].get('note', '')}" if bad else "")})
    st.dataframe(rows, hide_index=True, use_container_width=True)
    q429 = [r["Model"] for r in rows if r["Quota refusals (429)"]]
    if q429:
        st.warning(f"Quota limit hit on {', '.join(q429)}: Google refused these calls (429), so each AI search waited for the refusal "
                   "and then tried the next model. On the free tier, check the daily (RPD) and per-minute (RPM) limits in Google AI Studio.")

    st.markdown('<div class="layer">Gemini calls · newest first</div>', unsafe_allow_html=True)
    if calls:
        ev = st.dataframe([{"Time": _clock(c["at"]), "Purpose": c["purpose"], "Model": c["model"],
                       "Result": "OK" if c["status"] == 200 else f"✕ {c['status']}", "Seconds": c["secs"],
                       "Prompt tokens": c.get("prompt_tokens"), "Cached tokens": c.get("cached_tokens"),
                       "Thinking tokens": c.get("thinking_tokens"), "Output tokens": c.get("output_tokens"),
                       "Error": c.get("note", "")} for c in reversed(calls)], hide_index=True, use_container_width=True,
                          on_select="rerun", selection_mode="single-row", key="adm_calls")
        st.caption("Seconds is Google's response time. Thinking tokens are the model's hidden reasoning: more thinking, slower answer. "
                   "Tick a row, then open it to see exactly what was sent and what Gemini replied.")
        pick = ev.selection.rows
        if st.button("🔍 View this call (sent + reply)", disabled=not pick, key="adm_call_btn"):
            _call_detail(list(reversed(calls))[pick[0]])
    else:
        st.info("No Gemini calls yet. " + ("Run an AI search (a full sentence) and refresh." if API_KEY else
                                         "There is no GEMINI_API_KEY, so the app is using offline rules."))

    st.markdown('<div class="layer">Searches · all visitors, newest first</div>', unsafe_allow_html=True)
    if searches:
        ev = st.dataframe([{"Time": _clock(x["at"]), "Visitor": x["sid"], "Profile": x["profile"], "Query": x["q"],
                       "Path": {"agent": "AI", "keyword": "normal", "help": "customer care"}.get(x["kind"], x["kind"])
                               + (" (safety net)" if x["fallback"] else "") + (" · cached" if x["cached"] else ""),
                       "Stage": x["stage"], "Results": x["n"], "Total (s)": round(x["t"], 2),
                       "AI wait (s)": round(x["t_ai"], 2) if x["t_ai"] is not None else None,
                       "App work (s)": round(x["t"] - (x["t_ai"] or 0), 2), "Model": x["model"] or ""}
                      for x in reversed(searches)], hide_index=True, use_container_width=True,
                          on_select="rerun", selection_mode="single-row", key="adm_searches")
        st.caption("AI wait = time spent waiting for Gemini (all models tried). App work = everything else: routing, searching "
                   "5,000+ products, size checks. Tick a row, then open its full log.")
        pick = ev.selection.rows
        if st.button("🔍 View full log of this search", type="primary", disabled=not pick, key="adm_search_btn"):
            _search_detail(list(reversed(searches))[pick[0]])
    else:
        st.info("No searches yet.")

    _prerun_panel()

    with st.expander("Configuration"):
        st.markdown(f"- **Catalog:** {html.escape(CATALOG_SOURCE)} · {len(PRODUCTS):,} products\n"
                    f"- **Models (GEMINI_MODELS):** {', '.join(MODELS)}\n"
                    f"- **Thinking:** the model's default (no cap) · **Time limit per AI call:** {A.TIMEOUT[1]}s, then the next model "
                    f"(order now: {', '.join(A.model_order(MODELS))})\n"
                    f"- **AI answers cached:** {len(_intent_cache())} (identical searches skip Gemini)\n"
                    f"- **This visitor:** {S.sid} · Streamlit {st.__version__} · Python {sys.version.split()[0]}")

# ------------------------------------------------------------------ trace
def render_trace(res):
    r = res["route"]
    st.markdown(f'<div class="step"><b>Router</b> · {html.escape(r["label"])} — {html.escape(r["reason"])}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="step"><b>Catalog</b> · {html.escape(CATALOG_SOURCE)}; ratings, sizes and fit data are not in the source data '
                '(sizes and fit are simulated)</div>', unsafe_allow_html=True)
    for name, arg, out in res["steps"]:
        st.markdown(f'<div class="step"><b>{html.escape(name)}</b> · <span class="tool">{html.escape(str(arg))}</span><br>{html.escape(str(out))}</div>', unsafe_allow_html=True)
    if res["kind"] != "help":
        st.markdown('<div class="step"><b>Fit agent (Layer 2)</b> · size + confidence computed for every result from fit reviews and your profile. '
                    'Fit signals and fit-review counts are simulated in this demo.</div>', unsafe_allow_html=True)


def view_trace():
    res = S.result
    if not res:
        st.info("No search yet. Search for something, or run one of the 🧪 Test cases, then come back here to see every step the agent took.")
        return
    r = res["route"]
    stage = r["stage"] if r["stage"] != "agent" else res.get("intent", {}).get("stage", 1)
    st.markdown(f'<div class="trace-q">“{html.escape(res["query"])}”</div>'
                f'<div class="router">{pill(stage)}<span>{html.escape(r["label"])} · {res["t"]:.2f}s</span></div>', unsafe_allow_html=True)
    t1, t2 = st.columns([1.15, 1])
    with t1:
        st.markdown('<div class="layer">Steps</div>', unsafe_allow_html=True)
        render_trace(res)
    with t2:
        if res["kind"] == "agent":
            st.markdown('<div class="layer">Verifier: each result against each constraint</div>', unsafe_allow_html=True)
            if res["items"]:
                rows = [{"#": k + 1, "product": p["name"][:34], "₹": p["price"],
                         **{n: mark(ok) for n, ok, _ in checks}} for k, (p, checks) in enumerate(res["items"])]
                st.dataframe(rows, hide_index=True, use_container_width=True)
                st.caption("✓ passes · ✕ fails · ? the listing doesn't state it (allowed only for inferred fabrics, ranked lower)")
            else:
                st.caption("Nothing passed the hard constraints.")
            st.markdown('<div class="layer">Structured intent (what the model returned)</div>', unsafe_allow_html=True)
            st.json(res["intent"], expanded=True)
        elif res["kind"] == "keyword":
            st.markdown('<div class="layer">Keyword results</div>', unsafe_allow_html=True)
            st.dataframe([{"#": k + 1, "product": PRODUCTS[i]["name"][:60], "₹": PRODUCTS[i]["price"]} for k, i in enumerate(res["items"])],
                         hide_index=True, use_container_width=True)
        else:
            st.caption("Out-of-scope query: no catalog search ran.")

# ------------------------------------------------------------------ views
def product_card(p, i=None, checks=None, intent=None, numbered=True, highlight=False):
    """One grid card: image with rating, brand, name, price, why line, fit badge, honest-note chip, View/Add.
    In search results the top three are highlighted (#1 best match, #2-3 top picks)."""
    ribbon = ("Best match" if i == 1 else "Top pick" if i in (2, 3) else None) if highlight else None
    marker = "pc best" if ribbon == "Best match" else "pc top" if ribbon else "pc"
    with st.container(border=True):
        if intent:
            why = f'<div class="why">✦ {html.escape(A.why_this(p, intent))}</div>'
        else:
            why = f'<div class="why sub">{html.escape(" · ".join(x for x in (p["type"].title(), p["colour"]) if x))}</div>'
        ck = ""
        if checks:
            ck = '<div class="chk">' + " ".join(f"{mark(ok)} " + html.escape(n) for n, ok, _ in checks) + "</div>"
        st.markdown(f'<span class="{marker}"></span>{image_block(p, i if numbered else None, ribbon=ribbon)}<div class="pbrand">{html.escape(p["brand"])}</div>'
                    f'<div class="pname" title="{html.escape(p["name"])}">{html.escape(p["name"])}</div>{price_block(p)}{why}'
                    f'<div class="foot">{fit_badge(p)}<br>{risky_note(p)}{ck}</div>', unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        if b1.button("View", key=f"v{p['id']}{i}", use_container_width=True):
            S.pid, S.view = p["id"], "product"; st.rerun()
        if b2.button("Add", key=f"a{p['id']}{i}", use_container_width=True, type="primary"):
            fa = A.fit_agent(p, S.profile)
            if fa and (not fa["size"] or fa["confidence"] == "low"):   # never a confident guess: let the shopper pick
                S.pid, S.view = p["id"], "product"
                st.toast("We're not sure of your size for this one. Answer one question or check the size chart."); st.rerun()
            size = (fa or {}).get("size") or p["sizes"][min(2, len(p["sizes"]) - 1)]
            S.cart.append(dict(id=p["id"], size=size)); record_add(p, size, fa)
            st.toast(f"Added {p['name']} ({size})"); st.rerun()

def grid(items, intent=None, ncols=4, numbered=True, highlight=False):
    for r0 in range(0, len(items), ncols):
        cols = st.columns(ncols)
        for k, it in enumerate(items[r0:r0 + ncols]):
            p, checks = (it if isinstance(it, tuple) else (it, None))
            with cols[k]:
                product_card(p, r0 + k + 1, checks, intent, numbered, highlight)


@st.cache_data(show_spinner=False)
def cached_browse(dept, ptype, sort):
    return A.browse(dept, ptype, sort)


SUGGESTIONS = ["T-shirt for gym & running", "Kurta for office under ₹1,500", "Saree for a wedding", "Lilac dress for brunch",
               "Linen shirt for summer", "Warm jacket for winter"]


def run_suggestion(sq):
    S.q = sq
    run_search(sq)
    go_tab(TABS[0])


def _reset_home():
    S.home_n = 24


def view_home():
    st.markdown(f'<div class="hero"><div><div class="hero-t">Shop {len(PRODUCTS):,} products</div>'
                '<div class="hero-s">Browse below, or describe what you need in the search bar: AI mode understands occasions, '
                'weather, budget and fit. New here? Take the 2-minute tour in 📖 Tutorial.</div></div></div>', unsafe_allow_html=True)
    prefs = profile_prefs(S.profile)
    if any(prefs[f] for f in prefs):
        ordered = {o["pid"] for o in S.profile.get("orders", [])}
        recs = A.recommend(prefs, S.profile.get("gender"), exclude=ordered, k=4)
        if recs:
            top_types = ", ".join(t for t, _ in prefs["type"].most_common(2))
            src = "past orders" + (" and what you've searched" if S.profile.get("behaviour") else "")
            st.markdown(f'<div class="sugg">PICKED FOR {html.escape(S.profile["name"].upper())} · BASED ON {src.upper()} ({html.escape(top_types)})</div>',
                        unsafe_allow_html=True)
            grid(recs, numbered=False)
    st.markdown('<div class="sugg">POPULAR SEARCHES · TAP TO TRY AI MODE</div>', unsafe_allow_html=True)
    sc = st.columns(len(SUGGESTIONS))
    for c, sq in zip(sc, SUGGESTIONS):
        c.button(sq, key="sg" + sq, use_container_width=True, on_click=run_suggestion, args=(sq,))
    f1, f2, f3 = st.columns([4.2, 1.6, 1.4], vertical_alignment="bottom")
    with f1:
        g = S.profile.get("gender")   # the sidebar's "Shopping for" picks the starting department
        dept = st.segmented_control("Department", list(A.DEPARTMENTS), default={"women": "Women", "men": "Men"}.get(g, "All"),
                                    key=f"dept_{g}", on_change=_reset_home) or "All"
    types = cached_browse_types(dept)
    ptype = f2.selectbox("Type", ["All types"] + types, key=f"ptype_{dept}", on_change=_reset_home)
    sort = f3.selectbox("Sort", ["Featured", "Price: low to high", "Price: high to low"], key="sort", on_change=_reset_home)
    ids = cached_browse(dept, None if ptype == "All types" else ptype, sort)
    n = min(S.home_n, len(ids))
    st.markdown(f'<div class="rescount"><b>{len(ids):,}</b> products · showing {n}</div>', unsafe_allow_html=True)
    grid([PRODUCTS[i] for i in ids[:n]], numbered=False)
    if n < len(ids):
        _, mid, _ = st.columns([2, 1, 2])
        mid.button("Show more", use_container_width=True, key="more", on_click=lambda: S.__setitem__("home_n", S.home_n + 24))


@st.cache_data(show_spinner=False)
def cached_browse_types(dept):
    return A.browse_types(dept)


def tradeoff(intent, relaxed, items):
    """'Nothing in chanderi under ₹6,000. Here's the closest: … in cotton-silk at ₹5,800.'"""
    show = lambda v: " / ".join(v) if isinstance(v, list) else str(v)
    occ = {"wedding": "for a wedding", "haldi": "for a haldi", "sports": "for sports / gym", "office": "for office",
           "party": "for a party", "festive": "for festive wear", "casual": "for casual wear", "brunch": "for brunch"}
    names = {"fabrics": "in {}", "colours": "in {}", "colour_family": "in {} colours", "pairs": "that pairs with {}"}
    def phrase(k, v):
        if k == "occasion": return occ.get(v, f"for {v}")
        if k == "time": return "for daytime" if v == "day" else "for the evening"
        return names.get(k, "{}").format(show(v))
    asked = " and ".join(phrase(k, v) for k, v in relaxed)
    h = intent.get("hard", {})
    budget = f" under ₹{h['budget_max']:,}" if h.get("budget_max") else ""
    n_exact = sum(1 for _, checks in items if all(c[1] is not False for c in checks))
    if n_exact:
        dropped = ", ".join(k.replace("_", " ").replace("colours", "colour") for k, _ in relaxed)
        return (f"Only {n_exact} exact match{'es' if n_exact > 1 else ''} {asked}{budget}, shown first. "
                f"I've added close options without the {dropped} filter (marked ✕ on the card).")
    msg = f"Nothing {asked}{budget}."
    if items:
        p = items[0][0]
        got = {"fabrics": p["fabric"] or "another fabric", "colours": p["colour"], "colour_family": p["colour"],
               "pairs": p["pairs"], "time": p["time"], "occasion": None}.get(relaxed[0][0], "")
        msg += f" Here's the closest: {p['name']}{' in ' + got if got else ''} at ₹{p['price']:,}. Your other must-haves are kept."
    return msg


def _intent_summary(intent):
    """The agent's interpretation, or one built from the constraints (offline rules have no sentence of their own)."""
    txt = (intent.get("interpretation") or "").strip()
    if txt and not txt.startswith("Parsed with offline"):
        return txt
    h, s = intent.get("hard", {}), intent.get("soft", {})
    budget = (f" under ₹{h['budget_max']:,}" if h.get("budget_max") else "") + (f" over ₹{h['budget_min']:,}" if h.get("budget_min") and not h.get("budget_max") else "")
    extra = [x for x in (s.get("occasion") and f"for {s['occasion']}",) if x]
    d = describe(h.get("gender"), s.get("colours") or s.get("colour_family") or [], h.get("types") or [], h.get("size"), budget=budget,
                 style=h.get("style"), category=h.get("category"))
    return d + (" " + " ".join(extra) if extra else "")


def _why_notes(res, intent=None):
    """Short reasons under 'I understood': spelling fixes, mappings, profile, context tools."""
    notes = [f"fixed “{a}” → {b}" for a, b in res["route"].get("fixes", [])]
    notes += [f"fixed “{f['typed']}” → {f['meant']}" for f in (intent or {}).get("spelling", [])]
    for m in (intent or {}).get("mappings", []) or []:
        notes.append(f"“{m.get('phrase', '')}” → {m.get('maps_to', '')}")
    for name, arg, out in res.get("steps", []):
        if name == "Profile": notes.append(f"{out.split(' (')[0].replace('gender = ', '').title()} from your profile")
        if name == "Context tool" and "weather" in arg: notes.append(f"weather (AI estimate): {out}")
    return notes[:4]


def _fit_summary(products):
    """Fit layer result over the shown products: how many got a size, at which confidence."""
    conf = collections.Counter()
    for p in products:
        fa = A.fit_agent(p, S.profile)
        conf["n/a" if not fa else (fa["confidence"] if fa["size"] else "ask")] += 1
    sized = sum(v for k, v in conf.items() if k in ("high", "medium", "low"))
    if not products:
        return "no products to size"
    if not sized and conf["n/a"]:
        return "not clothing: no size needed"
    parts = [f"{conf[k]} {k}" for k in ("high", "medium", "low") if conf[k]]
    return f"size for {sized}/{len(products)} ({', '.join(parts) or 'none'})" + (f"; {conf['ask']} need one fit question" if conf["ask"] else "")


def agent_steps(res, products, relaxed=None, removed=()):
    """The agent loop from the solution doc, step by step, with what each step actually did in this search."""
    r = res["route"]
    steps = res.get("steps", [])
    find = lambda name: [o for n, _, o in steps if n == name]
    stage = r["stage"] if r["stage"] != "agent" else res.get("intent", {}).get("stage", 1)
    label = STAGE_PILL.get(stage, (str(stage),))[0]
    out = [("R", "Query router", "done", f"stage {label}")]
    if res["kind"] == "help":
        out.append(("→", "Help / support flow", "done", "not a product search: handed to Customer Care"))
        return out
    if res["kind"] == "keyword":
        skip = "fallback: AI unavailable" if res.get("fallback") else "skipped: simple query, no AI call"
        out += [("1", "Intent & constraints", "skip", skip), ("?", "Clarifier", "skip", "not needed"),
                ("2", "Context tools", "skip", "not needed"),
                ("3", "Search & ranking", "done", f"keyword search: {len(products)} items match every word"),
                ("4", "Verifier", "skip", "words must all match"), ("5", "Fit layer", "done", _fit_summary(products))]
        return out
    it = res["intent"]
    h, s = it.get("hard", {}), it.get("soft", {})
    nh = sum(1 for k, v in h.items() if v not in (None, [], ""))
    ns = sum(1 for k, v in s.items() if v not in (None, [], "", False) and k not in ("prefer_colour_family", "prefer_types", "climate", "weather", "layer_tip", "fabric_named"))
    model = res.get("model", "")
    memory = " · used previous search" if any("previous search" in o for o in find("Intent & constraints")) else ""
    fixes = find("Validator")
    val = "" if not fixes or fixes[0] == "all values valid" else " · validator fixed values"
    conf = it.get("confidence", "high")
    out.append(("1", "Intent & constraints", "relax" if conf == "low" else "done",
                f"{nh} hard, {ns} soft · {conf} confidence ({model}){memory}{val}"))
    cl = it.get("clarify") if it.get("stage") == 4 else None
    out.append(("?", "Clarifier", "ask" if cl else "skip", f"asked: {cl['question']}" if cl else "not needed: intent is clear enough"))
    tools = [o for n, a, o in steps if n == "Context tool"] + [f"{o.split(' (')[0].replace('gender = ', '').title()} (from your profile)" for o in find("Profile")]
    out.append(("2", "Context tools", "done" if tools else "skip", "; ".join(tools) if tools else "none needed"))
    attempts = [o for o in find("Catalog search + verifier") if o.startswith("Attempt")]
    first = attempts[0].split(": ", 1)[-1] if attempts else ""
    out.append(("3", "Search & ranking", "done", f"{first.split(', ')[0] if first else 'searched'}; ranked by fit to your preferences"))
    rel = relaxed if relaxed is not None else res.get("relaxed")
    if rel:
        what = ", ".join(f"{k.replace('_', ' ')} ({', '.join(v) if isinstance(v, list) else v})" for k, v in rel)
        out.append(("4", "Verifier", "relax", f"too few exact matches: relaxed {what}, re-searched"))
    else:
        out.append(("4", "Verifier", "done", f"{len(products)} passed every check" + (f" · you removed {len(removed)} filter(s)" if removed else "")))
    out.append(("5", "Fit layer", "done", _fit_summary(products)))
    return out


def steps_strip(steps):
    cells = "".join(f'<div class="st st-{status}"><div class="st-n">{html.escape(n)}</div><div class="st-t">{html.escape(t)}</div>'
                    f'<div class="st-d">{html.escape(d)}</div></div>' for n, t, status, d in steps)
    st.markdown(f'<div class="steps-h">How I got here</div><div class="steps">{cells}</div>', unsafe_allow_html=True)


def _quick_refines(res, products):
    """One-tap follow-ups that make sense for these results."""
    if not products:
        return []
    out = ["#1 but cheaper"]
    if ((res.get("intent") or {}).get("soft") or {}).get("layer_tip"):   # cold trip, light clothes asked for
        out.insert(0, "Add a warm layer: jackets & sweatshirts")
    prices = sorted(p["price"] for p in products)
    cap = int(round(prices[len(prices) // 2], -2))
    if cap >= 200:
        out.append(f"Under ₹{cap:,}")
    out.append("Show more like #1")
    g = (res.get("intent") or {}).get("hard", {}).get("gender") or (res.get("kw_filters") or {}).get("gender")
    if g in ("women", "men"):
        out.append(f"For {'men' if g == 'women' else 'women'} instead")
    return out


def _run_refine(text):
    run_search(text, followup=True)
    go_tab(TABS[0])


def refine_bar(res, products):
    """Follow-up box right under the reasoning bubble: the conversation continues where the shopper is looking."""
    with st.form(f"follow{id(res)}", clear_on_submit=True, border=False):
        f0, f1, f2 = st.columns([0.9, 5.2, 1], vertical_alignment="center")
        f0.markdown('<div class="refine-l">✦ Refine</div>', unsafe_allow_html=True)
        fq = f1.text_input("Refine", placeholder="Ask a follow-up… e.g. '#2 but cheaper', 'same in blue', 'something less heavy'",
                           label_visibility="collapsed")
        if f2.form_submit_button("Refine", use_container_width=True, type="primary") and fq.strip():
            run_search(fq.strip(), followup=True); st.rerun()   # already on Shop; tabs can't change mid-run
    quick = _quick_refines(res, products)
    if quick:
        qc = st.columns([0.9] + [1.25] * len(quick) + [max(0.1, 5.2 - 1.25 * len(quick))])
        qc[0].markdown('<div class="refine-q">Try:</div>', unsafe_allow_html=True)
        for c, t in zip(qc[1:], quick):
            c.button(t, key=f"qr{t}{id(res)}", use_container_width=True, on_click=_run_refine, args=(t,))


def filter_row(labels, key):
    """Applied filters, removable. Returns the labels the shopper removed."""
    if not labels:
        return []
    keep = st.multiselect("Filters applied · remove one to widen your results", labels, default=labels, key=key)
    return [l for l in labels if l not in keep]


def view_search():
    res = S.result
    if not res:
        view_home()
        return
    r = res["route"]
    stage = r["stage"] if r["stage"] != "agent" else res.get("intent", {}).get("stage", 1)
    rc1, rc2 = st.columns([6, 1.1], vertical_alignment="center")
    mode = {"agent": "✦ AI mode", "help": "Customer support", "keyword": "Quick search"}[res["kind"]]
    rc1.markdown(f'<div class="router">{pill(stage)}<span class="friendly">{mode} · {res["t"]:.1f}s</span></div>', unsafe_allow_html=True)
    rc2.button("🧠 AI trace", use_container_width=True, key="open_trace", on_click=go_tab, args=(TABS[3],))

    # ---------------- not a search: support or something else
    if res["kind"] == "help":
        intent = res.get("intent", {})
        reply = intent.get("reply")
        if res.get("qtype") == "other":
            bubble(res["query"], intent.get("interpretation") or "Not a shopping request", [],
                   html.escape(reply or "Nothing to search for, so here are some ideas to start with:"))
            sc = st.columns(len(SUGGESTIONS))
            for c, sq in zip(sc, SUGGESTIONS):
                c.button(sq, key="hs" + sq, use_container_width=True, on_click=run_suggestion, args=(sq,))
        else:
            bubble(res["query"], intent.get("interpretation") or "A customer-support request (orders, returns, refunds, payments or account)",
                   [], "<b>This isn’t a search query</b>, so I’m redirecting you to <b>Customer Care</b>. "
                   + html.escape(reply or "They handle returns, exchanges, refunds, order tracking, payments and your account."))
            h1, h2, _ = st.columns([1.3, 1.3, 3])
            if h1.button("💬 Open help chat", type="primary", use_container_width=True, key="helpchat"):
                st.info("Connecting you to a Customer Care agent… (demo: the help chat is not part of this prototype)")
            h2.button("← Back to shopping", use_container_width=True, key="helpback", on_click=go_home)
        steps_strip(agent_steps(res, []))
        if show_trace:
            with st.expander("🧠 Agent trace: what SearchSense did", expanded=False):
                render_trace(res)
        return

    # ---------------- normal (keyword) search
    if res["kind"] == "keyword":
        f = res.get("kw_filters") or A.keyword_filters(r["query"], S.profile.get("gender"))
        chips = kw_chips(f)
        top = st.container()   # the bubble shows above the filters but is written after them (it reflects removals)
        removed = {c for c in filter_row([c[0] for c in chips], f"kwf{id(res)}")} if chips else set()
        items_ids = res["items"]
        if removed:   # rebuild the query from the filters that are left
            kept = [c for c in chips if c[0] not in removed]
            q2 = " ".join(v for _, kind, v in kept if kind != "gender")
            g2 = next((v for _, kind, v in kept if kind == "gender"), None)
            items_ids = [p["id"] for p in A.keyword_search(q2, max_results=24, gender=g2)] if q2.strip() else []
            f = dict(f, gender=g2, types=[t for t in f["types"] if any(k == "type" and v == t[0] for _, k, v in kept)],
                     colours=f["colours"] if any(k == "colour" for _, k, _ in kept) else [],
                     size=f["size"] if any(k == "size" for _, k, _ in kept) else None,
                     words=[w for w in f["words"] if any(k == "word" and v == w for _, k, v in kept)])
        items = [PRODUCTS[i] for i in items_ids]
        understood = describe(f.get("gender"), [c for c, _ in f.get("colours", [])], [t for t, _ in f.get("types", [])],
                              f.get("size"), extra=f.get("words", []))
        why = _why_notes(res) + (["gender from your profile"] if f.get("gender_from") == "profile" and f.get("gender") else [])
        unknown = [w for w in (res.get("kw_info") or {}).get("unknown", []) if w not in (r.get("did_you_mean") or {})]
        if unknown:
            why.append("didn't recognise " + ", ".join(f"“{w}”" for w in unknown) + ", so I searched without it")
        partial = (res.get("kw_info") or {}).get("mode", "").startswith("partial")
        if items:
            showing = (f"<b>{len(items)}</b> {html.escape(understood.lower() if understood != 'products' else 'products')}"
                       + (", closest matches (nothing matched every word)" if partial else ", every one matching all your filters, best matches first"))
        else:
            showing = "nothing yet. Try describing what you need, e.g. “yellow t-shirt for the gym under ₹800”."
        with top:
            bubble(res["query"], understood, why, showing)
            dym = r.get("did_you_mean") or {}
            if dym:   # not sure which word was meant: ask instead of guessing
                for word, options in dym.items():
                    st.markdown(f'<div class="ask">🤔 <b>Did you mean</b> … for “{html.escape(word)}”?</div>', unsafe_allow_html=True)
                    dc = st.columns(len(options) + 3)
                    for c, o in zip(dc, options):
                        fixed = re.sub(rf"\b{re.escape(word)}\b", o, res["query"], flags=re.I)
                        c.button(o, key=f"dym{word}{o}", type="primary", use_container_width=True, on_click=run_suggestion, args=(fixed,))
            refine_bar(res, items)
            steps_strip(agent_steps(res, items))
        if r.get("fixes"):
            st.button(f"Search instead for “{res['query']}”", key="undo", on_click=run_search, args=(res["query"],), kwargs=dict(exact=True))
        if res.get("fallback"):
            st.info("AI mode is unavailable right now, so these are normal search results for your words.")
        S.last_results = items_ids
        if items:
            grid(items, highlight=True)
        if show_trace:
            with st.expander("🧠 Agent trace: what SearchSense did", expanded=False):
                render_trace(res)
        return

    # ---------------- AI mode
    intent = res["intent"]
    chips = chips_from(intent)
    top = st.container()   # bubble, question and steps above the filters, written after them
    removed = filter_row([c[0] for c in chips], f"chips{id(res)}")
    items, relaxed = res["items"], res["relaxed"]
    if removed:
        items, relaxed, _, _ = A.search(apply_removed(intent, removed), max_results=8)
    must = sum(1 for c in chips if c[1] == "hard" and c[0] not in removed)
    if intent.get("query_type") == "out_of_catalog":
        showing = html.escape(intent.get("reply") or "We don’t sell this here yet.") + (f" <b>{len(items)}</b> alternatives below." if items else "")
    elif intent.get("stage") == 4 and intent.get("clarify"):
        showing = f"<b>{len(items)}</b> options for now. One quick question will narrow them down:"
    elif relaxed:
        showing = html.escape(tradeoff(intent, relaxed, items))
    elif items:
        showing = (f"<b>{len(items)}</b> results, each checked against your {must} must-have{'s' if must != 1 else ''} and your preferences, "
                   "best match first, with a size suggestion on each")
    else:
        showing = "nothing that meets every must-have. Remove a filter, or see the closest options below."
    sw = intent.get("soft", {})
    if sw.get("layer_tip") and sw.get("weather"):   # e.g. t-shirts for Manali: give them, but say it's cold
        w = sw["weather"]
        when = (sw.get("month") or datetime.date.today().strftime("%B")).title()
        showing += (f" <b>Heads-up:</b> {html.escape((sw.get('city') or 'it').title())} is {html.escape(w.get('note') or w['climate'])}"
                    + (f" (about {w['temp_c']}°C)" if w.get("temp_c") is not None else "") + f" in {when}, so you may want a warm layer too.")
    low_conf = intent.get("confidence") == "low"
    if low_conf:
        showing += " <i>I’m not fully sure I understood, so normal search results for your words are further down too.</i>"
    with top:
        bubble(res["query"], _intent_summary(intent), _why_notes(res, intent), showing)
        if intent.get("spelling"):   # Rohan: typos are fixed silently, with a one-tap undo
            st.button(f"Search instead for “{res['query']}”", key="undo_ai", on_click=run_search, args=(res["query"],),
                      kwargs=dict(exact=True))
        # clarifier (stage 4): the agent decided one answer would change the results, so it asks
        if intent.get("stage") == 4 and intent.get("clarify"):
            cq = intent["clarify"]
            st.markdown(f'<div class="ask">🤔 <b>One quick question:</b> {html.escape(cq["question"])}</div>', unsafe_allow_html=True)
            oc = st.columns(len(cq["options"]) + 2)
            for c, o in zip(oc, cq["options"]):
                if c.button(o, key="cl" + o, use_container_width=True, type="primary"):
                    run_search(f"{res['query']} — {o}"); st.rerun()
        refine_bar(res, [p for p, _ in items])
        steps_strip(agent_steps(res, [p for p, _ in items], relaxed, removed))

    S.last_results = [p["id"] for p, _ in items]
    if items:
        grid(items, intent, highlight=True)
        if low_conf:   # safety net: the agent wasn't sure, so the shopper also gets plain search
            kw = A.keyword_search(res["query"], max_results=8, gender=S.profile.get("gender"))
            if kw:
                st.markdown('<div class="rescount">Normal search results for your words</div>', unsafe_allow_html=True)
                grid(kw, numbered=False)
    else:
        if res.get("near"):
            st.caption("Closest options if you can stretch the budget:")
            grid([PRODUCTS[i] for i in res["near"]])
        else:   # safety net: never a dead end
            kw = A.keyword_search(res["query"], max_results=8, gender=S.profile.get("gender"))
            if kw:
                st.caption("Normal search results for your words:")
                grid(kw)

    if show_trace:
        with st.expander("🧠 Agent trace: what SearchSense did", expanded=False):
            render_trace(res)
            st.json(intent, expanded=False)

PRODUCT_QUESTIONS = ["Is it see-through?", "Does it run small?", "Good for humid weather?", "How do I wash it?"]


def cached_ask(p, q):
    """Product questions reuse a saved AI answer (from earlier visitors or the demo pre-run); fallback answers aren't saved."""
    key = (p["id"], q.strip().lower())
    if key in _qa_cache():
        return _qa_cache()[key]
    ans, src = A.ask_product(p, q, API_KEY, MODELS)
    if API_KEY and not src.startswith("listing"):
        _qa_cache()[key] = (ans, src)
    return ans, src


def _ask(p, q):
    ans, src = cached_ask(p, q)
    S.setdefault("qa", {}).setdefault(p["id"], []).append((q, ans, src))


def product_qa(p):
    """Ask the AI about this product (preview: answers come only from the listing and review notes we have)."""
    st.markdown('<div class="layer">💬 Ask about this product</div>', unsafe_allow_html=True)
    qc = st.columns(len(PRODUCT_QUESTIONS))
    for c, q in zip(qc, PRODUCT_QUESTIONS):
        c.button(q, key=f"pq{p['id']}{q}", use_container_width=True, on_click=_ask, args=(p, q))
    with st.form(f"ask{p['id']}", clear_on_submit=True, border=False):
        f1, f2 = st.columns([5, 1])
        q = f1.text_input("Question", placeholder="e.g. Will the colour look different in daylight?", label_visibility="collapsed")
        if f2.form_submit_button("Ask", use_container_width=True) and q.strip():
            _ask(p, q.strip())
    for q, ans, src in reversed(S.get("qa", {}).get(p["id"], [])[-4:]):
        st.markdown(f'<div class="qa"><div class="qa-q">You: {html.escape(q)}</div><div class="qa-a">✦ {html.escape(ans)}</div>'
                    f'<div class="qa-s">Based on: {html.escape(src)}</div></div>', unsafe_allow_html=True)
    st.caption("Preview: answers use only this listing's details and the review notes we have. "
               "With full review data, answers will quote shoppers who bought it.")


def view_product():
    p = PRODUCTS[S.pid]
    if st.button("← Back"):
        S.view = "search"; st.rerun()
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown(image_block(p, tall=True), unsafe_allow_html=True)
    with c2:
        rating = f"{p['rating']}★" if p.get("rating") else ""
        meta = " · ".join(x for x in (p["fabric"].title(), p["colour"], ", ".join(p["occasions"]), rating) if x)
        st.markdown(f"<div class='pbrand' style='font-size:18px'>{html.escape(p['brand'])}</div>"
                    f"<h3 style='margin:0;font-weight:400;color:var(--mute)'>{html.escape(p['name'])}</h3>"
                    f"<div style='font-size:20px;margin:6px 0'>{price_block(p)}</div>"
                    f"<div class='why'>{html.escape(meta)}</div>", unsafe_allow_html=True)
        st.markdown('<div class="layer">Size &amp; fit</div>', unsafe_allow_html=True)
        fa = A.fit_agent(p, S.profile)
        low = bool(fa) and (not fa["size"] or fa["confidence"] == "low")
        if fa:
            if fa["size"] and not low:
                head = f"Take {fa['size']}" if fa["confidence"] == "high" else f"{fa['size']} recommended · medium confidence"
                st.markdown(f'<span class="badge b-{fa["confidence"]}" style="font-size:14px">{head}</span>'
                            f'<div class="why">{html.escape(fa["reason"])}</div>', unsafe_allow_html=True)   # the reason already has the review signal
            elif low:
                st.markdown('<span class="badge b-low" style="font-size:14px">Low confidence: we won’t guess your size</span>'
                            f'<div class="why">{html.escape(fa["reason"])}. Answer one question below, or use the size chart.</div>',
                            unsafe_allow_html=True)
            if fa.get("simulated"):
                st.caption("Demo note: fit reviews and available sizes are simulated, not real shopper data.")
            if fa.get("ask"):
                st.markdown(f"**One quick fit question:** {fa['ask']}")
                a1, a2, a3 = st.columns([2, 1, 1])
                brand = a1.selectbox("Brand", [b for b in ANCHOR_BRANDS if b != "None / not sure"] + [OTHER_BRAND], key="fqb")
                if brand == OTHER_BRAND:
                    brand = a1.text_input("Type the brand", key="fqb_typed", placeholder="e.g. Uniqlo").strip() or None
                scale = WAIST_ORDER if p["sizes"][0].isdigit() else SIZE_ORDER
                sz = a2.selectbox("Your size", scale, index=2, key="fqs")
                a3.button("Check fit", use_container_width=True, disabled=not brand, on_click=set_anchor, args=(brand, sz))
                if low:
                    with st.expander("Rather not answer? Size chart with key measurements", expanded=True):
                        st.dataframe([{"Size": k, **v} for k, v in (WAIST_CHART if scale is WAIST_ORDER else TOP_CHART).items() if k in p["sizes"]],
                                     hide_index=True, use_container_width=True)
                        st.caption("Standard Indian size chart (illustrative). Measure yourself and pick the size whose numbers sit just above yours.")
        else:
            st.caption("Fit check not needed for this product.")
        st.markdown('<div class="layer">Fit &amp; fabric tips</div>', unsafe_allow_html=True)
        for n in p["notes"]:
            st.markdown(f'<span class="note">💡 {html.escape(n)}</span>', unsafe_allow_html=True)
        if p["reviews"]:
            st.caption("Reviews: " + " · ".join(f"“{r}”" for r in p["reviews"]))
        elif not p["notes"]:
            st.caption("No review notes for this listing.")
        product_qa(p)
        rec = None if low else (fa or {}).get("size")
        idx = p["sizes"].index(rec) if rec in p["sizes"] else (None if low else 0)
        size = st.radio("Size", p["sizes"], index=idx, horizontal=True, key=f"sz{p['id']}{rec}")   # resets when the recommendation changes
        if st.button("Add to cart", type="primary", disabled=size is None, help="Pick a size first" if size is None else None):
            S.cart.append(dict(id=p["id"], size=size)); record_add(p, size, fa)
            st.toast("Added to cart"); st.rerun()
    look = A.complete_look(p)
    if look:
        st.markdown('<div class="layer">👗 Complete the look · preview</div>', unsafe_allow_html=True)
        st.caption("Pieces that usually go with this, matched by type, colour and budget from this catalog. "
                   "Preview of the look builder on our roadmap; footwear and jewellery aren't in this catalog yet.")
        grid(look, numbered=False)

def view_cart():
    if st.button("← Back"):
        S.view = "search"; st.rerun()
    st.markdown("### Your cart")
    if not S.cart:
        st.info("Your cart is empty."); return
    total = 0
    for k, it in enumerate(S.cart):
        p = PRODUCTS[it["id"]]; total += p["price"]
        c0, c1, c2, c3 = st.columns([0.6, 5, 1.2, 1], vertical_alignment="center")
        c0.markdown(image_block(p), unsafe_allow_html=True)
        c1.markdown(f"<div class='pbrand'>{html.escape(p['brand'])}</div><div class='pname'>{html.escape(p['name'])}</div>"
                    f"<div class='why'>Size {it['size']}</div>", unsafe_allow_html=True)
        c2.markdown(price_block(p), unsafe_allow_html=True)
        if c3.button("Remove", key=f"rm{k}"):
            S.cart.pop(k); st.rerun()
    st.markdown(f"<div class='price' style='font-size:18px;margin:10px 0'>Total: ₹{total:,}</div>", unsafe_allow_html=True)
    st.markdown('<div class="layer">Pre-checkout return-risk check</div>', unsafe_allow_html=True)
    risks = A.precheckout(S.cart, S.profile)
    if not [r for r in risks if r["level"] != "info"]:
        st.success("No size or bracketing risks found. 👍")
    shown_key = tuple((r["pid"], r["kind"]) for r in risks if r["fix"])
    if shown_key and S.get("_nudges_seen") != shown_key:
        S._nudges_seen = shown_key; S.metrics["nudges_shown"] += len(shown_key)
    for j, r in enumerate(risks):
        st.markdown(f'<div class="risk-{r["level"]}">{html.escape(r["msg"])}</div>', unsafe_allow_html=True)
        if r["fix"]:
            act, size = r["fix"]
            if st.button(f"{'Keep only' if act == 'keep' else 'Switch to'} {size}", key=f"fix{j}"):
                S.metrics["nudges_accepted"] += 1
                if act == "keep":
                    S.cart = [c for c in S.cart if not (c["id"] == r["pid"] and c["size"] != size)]
                    S.cart = [c for n, c in enumerate(S.cart) if not (c["id"] == r["pid"] and any(d["id"] == r["pid"] for d in S.cart[:n]))]
                else:
                    for c in S.cart:
                        if c["id"] == r["pid"]: c["size"] = size
                st.rerun()
    if st.button("Place order (demo)", type="primary"):
        S.metrics["orders"] += 1; S.metrics["ordered_items"] += len(S.cart)
        st.balloons(); st.success("Order placed (demo). Fewer surprises, fewer returns.")

if S.tab == TABS[1]:
    view_tutorial()
elif S.tab == TABS[2]:
    view_tests()
elif S.tab == TABS[3]:
    view_trace()
elif S.tab == TABS[4]:
    view_metrics()
elif S.tab == TABS[5]:
    view_admin()
else:
    {"search": view_search, "product": view_product, "cart": view_cart}[S.view]()
