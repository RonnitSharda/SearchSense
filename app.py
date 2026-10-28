import os, re, time, html, json
import streamlit as st
from catalog import PRODUCTS, SIZE_ORDER, WAIST_ORDER, ANCHOR_BRANDS, BREATHABLE, CATALOG_SOURCE
import agent as A
from ui import CSS, image_block, price_block

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

# ------------------------------------------------------------------ state
S = st.session_state
S.setdefault("view", "search")
S.setdefault("cart", [])
S.setdefault("history", [])
S.setdefault("result", None)
S.setdefault("pid", None)
S.setdefault("profile", dict(usual_size=None, waist=None, anchor_brand=None, anchor_size=None, past_brands=[]))
S.setdefault("removed_chips", [])
S.setdefault("fit_answer", {})
S.setdefault("last_results", [])
TABS = ["🏠 Shop", "🧪 Test cases", "🧠 AI trace"]
S.setdefault("tab", TABS[0])
S.setdefault("last_tab", TABS[0])
S.setdefault("home_n", 24)

# ------------------------------------------------------------------ helpers
STAGE_PILL = {0: ("0 · Pass-through", "p-grey"), 1: ("1 · Clear intent", "p-navy"), 2: ("2 · Minor correction", "p-navy"),
              3: ("3 · Major semantic", "p-pink"), 4: ("4 · Ambiguous", "p-amber"), 5: ("5 · No exact match", "p-navy"),
              6: ("6 · Out of scope", "p-grey")}

def pill(stage):
    t, c = STAGE_PILL.get(stage, (str(stage), "p-navy"))
    return f'<span class="pill {c}">{t}</span>'

def fit_badge(p):
    fa = A.fit_agent(p, S.profile)
    if not fa: return ""
    if fa["size"]:
        return f'<span class="badge b-{fa["confidence"]}">Size {fa["size"]} · {fa["confidence"]} confidence</span>'
    return '<span class="badge b-low">Size: low confidence · tap to check fit</span>'

def risky_note(p):
    for n in p["notes"]:
        if "not see" in n.lower(): continue
        if any(w in n.lower() for w in ["runs small", "runs slightly large", "sheer", "see-through", "peach", "heavy", "creases", "fragrance", "cool white", "relaxed"]):
            return f'<span class="note">💡 {html.escape(n)}</span>'
    return ""

@st.cache_resource
def _intent_cache():
    return {}


def cached_understand(query, history, _key, models, previous=""):
    """Identical queries reuse the agent's answer (saves quota and latency). Failures are never cached."""
    import copy
    cache, key = _intent_cache(), (query, history, models, previous)
    if key in cache:
        intent, model, log = copy.deepcopy(cache[key])
        return intent, model, log + ["served from cache"]
    out = A.understand(query, _key, list(models), list(history), json.loads(previous) if previous else None)
    if out[1] != "failed":
        if len(cache) > 500: cache.clear()
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
    h, s = intent.get("hard", {}), intent.get("soft", {})
    out = []
    if h.get("budget_min") and h.get("budget_max"): out.append((f"₹{h['budget_min']:,}–{h['budget_max']:,}", "hard", "budget"))
    elif h.get("budget_max"): out.append((f"Under ₹{h['budget_max']:,}", "hard", "budget"))
    elif h.get("budget_min"): out.append((f"Over ₹{h['budget_min']:,}", "hard", "budget"))
    if h.get("gender"): out.append((h["gender"].title(), "hard", "gender"))
    if h.get("style"): out.append((h["style"].title(), "hard", "style"))
    if h.get("types"): out.append((" / ".join(h["types"]), "hard", "types"))
    if h.get("size"): out.append((f"Size {h['size']}", "hard", "size"))
    if s.get("fabrics"): out.append((", ".join(sorted(s["fabrics"])[:4]) + ("…" if len(s["fabrics"]) > 4 else ""), "soft", "fabrics"))
    if s.get("colours"): out.append((" / ".join(s["colours"]).title(), "soft", "colours"))
    if s.get("colour_family"): out.append((" / ".join(s["colour_family"]).title(), "soft", "colour_family"))
    if s.get("occasion"): out.append((s["occasion"].title(), "soft", "occasion"))
    if s.get("time") and s["time"] != "any": out.append(("Daytime" if s["time"] == "day" else "Evening", "soft", "time"))
    if s.get("pairs") and s["pairs"] != "any": out.append((f"Pairs with {s['pairs']}", "soft", "pairs"))
    for n in s.get("needs") or []: out.append((n, "soft", "needs:" + n))
    return out

def apply_removed(intent, removed):
    import copy
    it = copy.deepcopy(intent)
    for label, sec, key in chips_from(intent):
        if label in removed:
            if key.startswith("needs:"):
                it["soft"]["needs"] = [n for n in it["soft"].get("needs", []) if n != key[6:]]
            elif key == "budget":
                it["hard"]["budget_min"] = it["hard"]["budget_max"] = None
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

def run_search(q, followup=False):
    t0 = time.time()
    S.removed_chips = []
    q_in = resolve_followup(q) if followup else q
    r = A.route(q_in if followup else q)
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
        if items or not API_KEY:
            res.update(kind="keyword", items=[p["id"] for p in items])
            S.last_results = res["items"]
        else:   # nothing matched the words: let the agent work out what the shopper meant
            res["steps"].append(("Escalation", "route()", "No keyword match, so the query goes to the AI agent"))
            r = res["route"] = dict(stage="agent", label="No keyword match: sent to agent", query=q, fixes=[],
                                    reason="Keyword search found nothing; the agent interprets the request")
    if r["stage"] == "agent":
        hist = tuple(S.history) if followup else tuple()
        prev = S.result.get("intent") if followup and S.result and S.result.get("kind") == "agent" else None
        intent, model, log = cached_understand(r["query"], hist, API_KEY, tuple(MODELS),
                                               json.dumps(prev, ensure_ascii=False, default=str) if prev else "")
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
        res.update(items=items, relaxed=relaxed, near=[p["id"] for p in near])
        S.last_results = [p["id"] for p, _ in items]
        S.history.append(f"{q} -> {intent.get('interpretation','')}")
    res["t"] = time.time() - t0
    S.result = res
    S.view = "search"


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

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### 👤 Your fit profile")
    st.caption("Used to recommend your size on every product, whichever way you search.")
    us = st.selectbox("Usual top size", ["Not set"] + SIZE_ORDER, index=3)
    wa = st.selectbox("Usual waist (jeans)", ["Not set"] + WAIST_ORDER, index=0)
    ab = st.selectbox("Brand that fits you best", list(ANCHOR_BRANDS.keys()), index=len(ANCHOR_BRANDS) - 1)
    gd = st.radio("Shopping for", ["Women", "Men", "Any"], horizontal=True)
    pb = st.multiselect("Brands you've bought here", sorted({p["brand"] for p in PRODUCTS.values()}))
    S.profile.update(usual_size=None if us == "Not set" else us, waist=None if wa == "Not set" else wa,
                     anchor_brand=None if ab == "None / not sure" else ab, past_brands=pb,
                     gender=None if gd == "Any" else gd.lower())
    S.profile.update(S.fit_answer)
    if S.fit_answer:
        st.caption(f"Fit answer saved: {S.fit_answer.get('anchor_brand')} {S.fit_answer.get('waist') or S.fit_answer.get('anchor_size')}")
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

n1, n2, n3 = st.columns([6.2, 1.2, 1.1], vertical_alignment="center")
with n1:
    st.segmented_control("Section", TABS, key="tab", on_change=_tab_changed, label_visibility="collapsed")
n2.button("🏠 All products", use_container_width=True, key="home_top", on_click=go_home)
n3.button(f"🛒 Cart ({len(S.cart)})", use_container_width=True, key="cart_top", on_click=open_cart)

# ------------------------------------------------------------------ test cases (scripted personas)
TEST_CASES = [
    dict(name="Rohan", icon="⌨️", tag="Stage 2 · typo", query="wite linnen shirt M",
         tests="Spelling correction and a size in a short query.",
         expect="“wite linnen” is fixed to “white linen” without asking; shirts stocked in M; fit badge on every card."),
    dict(name="Priya", icon="🌸", tag="Stage 3 · complex intent",
         query="breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery",
         tests="Subjective words mapped to attributes, plus weather and occasion tools.",
         expect="Breathable pastel ethnic sets under ₹6,000; the trace shows the Mumbai weather and day-wedding rules."),
    dict(name="Ananya", icon="👖", tag="Stage 1 · fit", query="high-waist straight jeans for office",
         tests="Fit agent when there is no size history.",
         expect="Jeans with a low-confidence size badge. Open one and answer the fit question to get a confident size; "
                "add two sizes to see the cart's ‘Keep only’ fix."),
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
    dict(name="Follow-up", icon="🔁", tag="Memory · refine", query="#2 but cheaper",
         setup="breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery",
         tests="Refining the previous search by pointing at a result.",
         expect="Runs Priya's search, then “#2 but cheaper”: the budget drops below result #2's price and the style is kept."),
]


def run_case(case):
    S.history, S.last_results = [], []   # each test case starts a fresh session
    if case.get("setup"):
        run_search(case["setup"])
        run_search(case["query"], followup=True)
    else:
        run_search(case["query"])
    S.q = case["query"]
    go_tab(TABS[0])


def view_tests():
    st.markdown('<div class="tc-intro"><b>Test cases</b> · nine scripted shoppers that exercise each part of the pipeline. '
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
            size = (fa or {}).get("size") or p["sizes"][min(2, len(p["sizes"]) - 1)]
            S.cart.append(dict(id=p["id"], size=size)); st.toast(f"Added {p['name']} ({size})"); st.rerun()

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
                'weather, budget and fit. Not sure what to try? Open 🧪 Test cases.</div></div></div>', unsafe_allow_html=True)
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
    names = {"fabrics": "in {}", "colours": "in {}", "colour_family": "in {} colours", "pairs": "that pairs with {}",
             "time": "for the {}", "occasion": "for a {}"}
    asked = " and ".join(names.get(k, "{}").format(show(v)) for k, v in relaxed)
    h = intent.get("hard", {})
    budget = f" under ₹{h['budget_max']:,}" if h.get("budget_max") else ""
    msg = f"Nothing {asked}{budget}."
    if items:
        p = items[0][0]
        got = {"fabrics": p["fabric"] or "another fabric", "colours": p["colour"], "colour_family": p["colour"],
               "pairs": p["pairs"], "time": p["time"], "occasion": ", ".join(p["occasions"][:2])}.get(relaxed[0][0], "")
        msg += f" Here's the closest: {p['name']}{' in ' + got if got else ''} at ₹{p['price']:,}. Your other must-haves are kept."
    return msg


def view_search():
    res = S.result
    if not res:
        view_home()
        return
    r = res["route"]
    stage = r["stage"] if r["stage"] != "agent" else res.get("intent", {}).get("stage", 1)
    rc1, rc2 = st.columns([6, 1.1], vertical_alignment="center")
    if res["kind"] == "agent":
        friendly = f"✦ <b>AI mode</b> read your request and checked every result against it ({res['t']:.1f}s)"
    elif res["kind"] == "help":
        friendly = "Not a product search" if res.get("qtype") != "other" else "Not a shopping request"
    elif r.get("fixes"):
        friendly = "Fixed spelling: " + ", ".join(f"“{html.escape(a)}” → <b>{html.escape(b)}</b>" for a, b in r["fixes"])
    else:
        friendly = f"Quick search for “{html.escape(r['query'])}”"
    rc1.markdown(f'<div class="router">{pill(stage)}<span class="friendly">{friendly}</span></div>', unsafe_allow_html=True)
    rc2.button("🧠 AI trace", use_container_width=True, key="open_trace", on_click=go_tab, args=(TABS[2],))

    if res["kind"] == "help":
        reply = res.get("intent", {}).get("reply")
        if res.get("qtype") == "other":
            st.markdown(f'<div class="helpbox"><div class="hb-t">🛍️ I can help you shop</div>'
                        f'<div class="hb-s">{html.escape(reply or "That is not something the search bar can help with. Tell me what you are shopping for, or try one of these:")}</div></div>',
                        unsafe_allow_html=True)
            sc = st.columns(len(SUGGESTIONS))
            for c, sq in zip(sc, SUGGESTIONS):
                c.button(sq, key="hs" + sq, use_container_width=True, on_click=run_suggestion, args=(sq,))
        else:
            st.markdown(f'<div class="helpbox"><div class="hb-t">💬 This isn’t a search query: redirecting you to Customer Care</div>'
                        f'<div class="hb-s">{html.escape(reply or "This sounds like a question for our support team.")} '
                        'Customer Care handles returns, exchanges, refunds, order tracking, payments and your account.</div></div>',
                        unsafe_allow_html=True)
            h1, h2, _ = st.columns([1.3, 1.3, 3])
            if h1.button("💬 Open help chat", type="primary", use_container_width=True, key="helpchat"):
                st.info("Connecting you to a Customer Care agent… (demo: the help chat is not part of this prototype)")
            h2.button("← Back to shopping", use_container_width=True, key="helpback", on_click=go_home)
        if show_trace:
            with st.expander("🧠 Agent trace: what SearchSense did", expanded=False):
                render_trace(res)
        return
    if res["kind"] == "keyword":
        if r.get("fixes"):
            u1, u2 = st.columns([3, 2])
            u1.markdown(f"Showing results for **{html.escape(r['query'])}**")
            if u2.button(f"Search instead for “{res['query']}”", key="undo"):
                items = [p["id"] for p in A.keyword_search(res["query"], max_results=24, gender=S.profile.get("gender"))]  # undo
                S.result = dict(res, route=dict(r, fixes=[], stage=0, reason="Undo: original words"), items=items); st.rerun()
        if res.get("fallback"):
            st.info("AI mode is unavailable right now, so these are normal search results for your words.")
        items = [PRODUCTS[i] for i in res["items"]]
        S.last_results = res["items"]
        if items:
            st.markdown(f'<div class="rescount"><b>{len(items)}</b> results · normal search, size check on every product</div>', unsafe_allow_html=True)
            grid(items, highlight=True)
        else:
            st.warning("No results. Try describing what you need.")
        if show_trace:
            with st.expander("🧠 Agent trace: what SearchSense did", expanded=False):
                render_trace(res)
        return

    intent = res["intent"]
    maps = "".join(f'<div class="map">• “{html.escape(m.get("phrase",""))}” → {html.escape(str(m.get("maps_to","")))}</div>' for m in intent.get("mappings", []) or [])
    st.markdown(f'<div class="aim"><div class="t">✦ What I understood</div>'
                f'<div class="i">{html.escape(intent.get("interpretation",""))}</div>{maps}</div>', unsafe_allow_html=True)
    if intent.get("query_type") == "out_of_catalog":
        st.markdown(f'<div class="relax">🛍️ {html.escape(intent.get("reply") or "We don’t sell this here yet.")}</div>', unsafe_allow_html=True)

    # clarifier (stage 4)
    if intent.get("stage") == 4 and intent.get("clarify"):
        cq = intent["clarify"]
        st.markdown(f"**{html.escape(cq['question'])}**")
        oc = st.columns(len(cq["options"]))
        for c, o in zip(oc, cq["options"]):
            if c.button(o, key="cl" + o, use_container_width=True):
                run_search(f"{res['query']} — {o}"); st.rerun()

    labels = [c[0] for c in chips_from(intent)]
    keep = st.multiselect("Edit what I understood (remove a chip to widen results):", labels, default=labels, key=f"chips{id(res)}")
    removed = [l for l in labels if l not in keep]
    items, relaxed = res["items"], res["relaxed"]
    if removed:
        it2 = A.apply_removed(intent, removed) if hasattr(A, "apply_removed") else apply_removed(intent, removed)
        items, relaxed, _, _ = A.search(it2, max_results=8)

    if relaxed:
        st.markdown(f'<div class="relax">⚖ {html.escape(tradeoff(intent, relaxed, items))}</div>', unsafe_allow_html=True)
    S.last_results = [p["id"] for p, _ in items]
    if items:
        st.markdown(f'<div class="rescount"><b>{len(items)}</b> results, each checked against your must-haves and your size</div>', unsafe_allow_html=True)
        grid(items, intent, highlight=True)
    else:
        st.warning("Nothing in the catalog meets your must-haves.")
        if res.get("near"):
            st.caption("Closest options if you can stretch the budget:")
            grid([PRODUCTS[i] for i in res["near"]])
        else:   # safety net: never a dead end
            kw = A.keyword_search(res["query"], max_results=8, gender=S.profile.get("gender"))
            if kw:
                st.caption("Normal search results for your words:")
                grid(kw)

    with st.form("follow", clear_on_submit=True, border=False):
        f1, f2 = st.columns([6, 1])
        fq = f1.text_input("Refine", placeholder="Ask a follow-up… e.g. '#2 but cheaper' or 'same but in lilac'", label_visibility="collapsed")
        if f2.form_submit_button("Refine", use_container_width=True) and fq.strip():
            run_search(fq.strip(), followup=True); st.rerun()

    if show_trace:
        with st.expander("🧠 Agent trace: what SearchSense did", expanded=False):
            render_trace(res)
            st.json(intent, expanded=False)

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
        if fa:
            if fa["size"]:
                st.markdown(f'<span class="badge b-{fa["confidence"]}" style="font-size:14px">Recommended: {fa["size"]} · {fa["confidence"]} confidence</span>'
                            f'<div class="why">{html.escape(fa["reason"])}</div>', unsafe_allow_html=True)
            if fa.get("simulated"):
                st.caption("Demo note: fit reviews and available sizes are simulated, not real shopper data.")
            if fa.get("ask"):
                st.markdown(f"**One quick fit question:** {fa['ask']}")
                a1, a2, a3 = st.columns([2, 1, 1])
                brand = a1.selectbox("Brand", [b for b in ANCHOR_BRANDS if b != "None / not sure"], key="fqb")
                scale = WAIST_ORDER if p["sizes"][0].isdigit() else SIZE_ORDER
                sz = a2.selectbox("Your size", scale, index=2, key="fqs")
                if a3.button("Check fit", use_container_width=True):
                    S.fit_answer["anchor_brand"] = brand
                    if scale is WAIST_ORDER: S.fit_answer["waist"] = sz
                    else: S.fit_answer["anchor_size"] = sz
                    st.rerun()
                if not fa["size"]:
                    with st.expander("Rather not answer? Size chart with key measurements"):
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
        rec = (fa or {}).get("size")
        idx = p["sizes"].index(rec) if rec in p["sizes"] else 0
        size = st.radio("Size", p["sizes"], index=idx, horizontal=True)
        if st.button("Add to cart", type="primary"):
            S.cart.append(dict(id=p["id"], size=size)); st.toast("Added to cart"); st.rerun()

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
    for j, r in enumerate(risks):
        st.markdown(f'<div class="risk-{r["level"]}">{html.escape(r["msg"])}</div>', unsafe_allow_html=True)
        if r["fix"]:
            act, size = r["fix"]
            if st.button(f"{'Keep only' if act == 'keep' else 'Switch to'} {size}", key=f"fix{j}"):
                if act == "keep":
                    S.cart = [c for c in S.cart if not (c["id"] == r["pid"] and c["size"] != size)]
                    S.cart = [c for n, c in enumerate(S.cart) if not (c["id"] == r["pid"] and any(d["id"] == r["pid"] for d in S.cart[:n]))]
                else:
                    for c in S.cart:
                        if c["id"] == r["pid"]: c["size"] = size
                st.rerun()
    if st.button("Place order (demo)", type="primary"):
        st.balloons(); st.success("Order placed (demo). Fewer surprises, fewer returns.")

if S.tab == TABS[1]:
    view_tests()
elif S.tab == TABS[2]:
    view_trace()
else:
    {"search": view_search, "product": view_product, "cart": view_cart}[S.view]()
