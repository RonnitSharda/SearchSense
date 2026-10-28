import os, re, time, html
import streamlit as st
from catalog import PRODUCTS, SIZE_ORDER, WAIST_ORDER, ANCHOR_BRANDS, BREATHABLE
import agent as A

st.set_page_config(page_title="SearchSense: agentic search MVP", page_icon="🔎", layout="wide")

# ------------------------------------------------------------------ config
def _secret(k, default=None):
    try:
        return st.secrets.get(k, os.environ.get(k, default))
    except Exception:
        return os.environ.get(k, default)

API_KEY = _secret("GEMINI_API_KEY")
MODELS = [m.strip() for m in _secret("GEMINI_MODELS", "gemini-flash-latest,gemini-flash-lite-latest,gemini-2.5-flash").split(",") if m.strip()]

CSS = """
<style>
:root{--navy:#1A1F5C;--pink:#E8336D;--pinkL:#FDE7EE;--card:#F4F5FA;--line:#D9DCEB;--mute:#6B6F86;--green:#1E9E6A;--greenL:#E3F6EE;--amber:#FFB020;--amberL:#FFF4DC;--red:#D93A3A;}
.block-container{padding-top:3.2rem;max-width:1300px}
.ss-top{display:flex;align-items:center;justify-content:space-between;background:var(--navy);color:#fff;border-radius:14px;padding:12px 20px;margin-bottom:14px}
.ss-logo{font-weight:800;font-size:24px;letter-spacing:-.5px}.ss-logo b{color:#FF7FA6}
.ss-sub{font-size:13px;opacity:.85}
.pill{display:inline-block;border-radius:20px;padding:3px 11px;font-size:12px;font-weight:700;margin:2px 4px 2px 0}
.p-navy{background:var(--navy);color:#fff}.p-pink{background:var(--pink);color:#fff}.p-amber{background:var(--amber);color:#3a2a00}
.p-green{background:var(--green);color:#fff}.p-grey{background:#8A8EA8;color:#fff}.p-red{background:var(--red);color:#fff}
.router{border:1.5px solid var(--line);border-radius:12px;padding:10px 14px;margin:6px 0 10px;background:#fff}
.router small{color:var(--mute)}
.aim{background:var(--pinkL);border-radius:12px;padding:10px 14px;margin-bottom:8px}
.aim .t{color:var(--pink);font-weight:800;font-size:12px;letter-spacing:.8px}
.aim .i{color:var(--navy);font-size:15px;margin-top:2px}
.map{font-size:13px;color:var(--navy);margin-top:4px}
.pcard{border:1.5px solid var(--line);border-radius:14px;padding:10px;background:#fff;height:100%}
.pimg{height:130px;border-radius:10px;display:flex;align-items:flex-end;justify-content:center;margin-bottom:8px}
.pname{font-weight:700;font-size:15px;line-height:1.25;color:#23253A}
.pbrand{font-size:12px;color:var(--mute)}
.price{font-weight:800;color:var(--navy);font-size:16px;margin:2px 0}
.why{font-size:12.5px;color:var(--mute);line-height:1.3;margin:2px 0 6px}
.badge{display:inline-block;font-size:11.5px;font-weight:700;padding:3px 8px;border-radius:7px;margin:2px 0}
.b-high{background:var(--greenL);color:#13724C}.b-medium{background:var(--amberL);color:#8A5A00}.b-low{background:#FDE8E8;color:var(--red)}
.note{font-size:11.5px;background:var(--amberL);color:#8A5A00;border-radius:7px;padding:3px 8px;display:inline-block;margin-top:3px}
.chk{font-size:11px;color:var(--mute)}
.relax{background:var(--amberL);border:1.5px solid var(--amber);border-radius:10px;padding:8px 12px;font-size:14px;margin:6px 0}
.layer{font-size:11px;font-weight:800;letter-spacing:1px;color:var(--mute);margin:4px 0}
.step{border-left:3px solid var(--pink);padding:4px 10px;margin:6px 0;font-size:13.5px}
.step b{color:var(--navy)}
.tool{font-family:monospace;font-size:12px;background:var(--card);border-radius:6px;padding:2px 6px}
.risk-high{border-left:5px solid var(--red);background:#FDE8E8;padding:8px 12px;border-radius:8px;margin:6px 0}
.risk-medium{border-left:5px solid var(--amber);background:var(--amberL);padding:8px 12px;border-radius:8px;margin:6px 0}
.risk-info{border-left:5px solid #8A8EA8;background:var(--card);padding:8px 12px;border-radius:8px;margin:6px 0;font-size:14px}
</style>"""
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

# ------------------------------------------------------------------ helpers
SILH = {
    "garment": '<svg width="64" height="104" viewBox="0 0 46 72"><path d="M15 4h16l5 10-5 6 13 48H2L15 20l-5-6z" fill="#fff" opacity=".85"/></svg>',
    "shirt": '<svg width="92" height="92" viewBox="0 0 60 60"><path d="M20 6l10 6 10-6 14 10-6 10-6-4v32H18V22l-6 4-6-10z" fill="#fff" opacity=".85"/></svg>',
    "jeans": '<svg width="70" height="104" viewBox="0 0 40 64"><path d="M6 2h28l2 60H24l-4-40-4 40H4z" fill="#fff" opacity=".85"/></svg>',
    "lamp": '<svg width="80" height="104" viewBox="0 0 50 64"><path d="M10 26 Q25 2 40 26z" fill="#fff" opacity=".9"/><rect x="23" y="26" width="4" height="28" fill="#fff" opacity=".9"/><rect x="14" y="54" width="22" height="5" rx="2" fill="#fff" opacity=".9"/></svg>',
    "bottle": '<svg width="60" height="104" viewBox="0 0 36 64"><rect x="12" y="2" width="12" height="10" rx="2" fill="#fff" opacity=".9"/><rect x="6" y="12" width="24" height="48" rx="6" fill="#fff" opacity=".9"/></svg>',
    "cushion": '<svg width="96" height="96" viewBox="0 0 60 60"><rect x="8" y="10" width="44" height="40" rx="10" fill="#fff" opacity=".85"/></svg>',
}
def silh(p):
    t = p["type"]
    if "shirt" in t or "jacket" in t: k = "shirt"
    elif "jeans" in t: k = "jeans"
    elif "lamp" in t: k = "lamp"
    elif p["category"] == "personal care": k = "bottle"
    elif "cushion" in t: k = "cushion"
    else: k = "garment"
    return f'<div class="pimg" style="background:linear-gradient(160deg,{p["swatch"]}55,{p["swatch"]})">{SILH[k]}</div>'

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
            return f'<span class="note">⚠ {html.escape(n)}</span>'
    return ""

@st.cache_data(show_spinner=False, ttl=3600)
def cached_understand(query, history, _key, models):
    return A.understand(query, _key, list(models), list(history))

def chips_from(intent):
    h, s = intent.get("hard", {}), intent.get("soft", {})
    out = []
    if h.get("budget_max"): out.append((f"Under ₹{h['budget_max']:,}", "hard", "budget_max"))
    if h.get("gender"): out.append((h["gender"].title(), "hard", "gender"))
    if h.get("style"): out.append((h["style"].title(), "hard", "style"))
    if h.get("types"): out.append((" / ".join(h["types"]), "hard", "types"))
    if h.get("size"): out.append((f"Size {h['size']}", "hard", "size"))
    if s.get("fabrics"): out.append((", ".join(sorted(s["fabrics"])[:4]) + ("…" if len(s["fabrics"]) > 4 else ""), "soft", "fabrics"))
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
        res.update(kind="help")
    elif r["stage"] in (0, 2):
        res.update(kind="keyword", items=[p["id"] for p in A.keyword_search(r["query"])])
    else:
        hist = tuple(S.history) if followup else tuple()
        intent, model, log = cached_understand(r["query"], hist, API_KEY, tuple(MODELS))
        res["steps"].append(("Intent & constraints", f"model: {model}", "; ".join(log)))
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
        items, relaxed, trace, near = A.search(intent)
        for t in trace: res["steps"].append(("Catalog search + verifier", "catalog_search()", t))
        if relaxed and intent.get("stage") != 4:
            intent["stage"] = 5
        res.update(items=items, relaxed=relaxed, near=[p["id"] for p in near])
        S.history.append(f"{q} -> {intent.get('interpretation','')}")
    res["t"] = time.time() - t0
    S.result = res
    S.view = "search"

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### 👤 Your fit profile")
    st.caption("Layer 2 uses this on every product, whatever search path you take.")
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
    show_trace = st.toggle("Show agent trace", value=True)
    st.markdown(f"**AI model:** {'Gemini (' + MODELS[0] + ')' if API_KEY else 'offline rules (no key set)'}")
    st.caption("Demo catalog: 25 illustrative products across fashion, lifestyle and personal care.")
    st.divider()
    if st.button(f"🛒 Cart ({len(S.cart)})", use_container_width=True):
        S.view = "cart"

# ------------------------------------------------------------------ header + search
st.markdown('<div class="ss-top"><div><div class="ss-logo">🔎 Search<b>Sense</b></div><div class="ss-sub">AI mode in the search bar · demo store</div></div>'
            '<div class="ss-sub">Layer 1: agentic search &nbsp;|&nbsp; Layer 2: fit &amp; return-risk on every path</div></div>', unsafe_allow_html=True)

with st.form("search", clear_on_submit=False, border=False):
    c1, c2 = st.columns([6, 1])
    q = c1.text_input("Search", placeholder="Search, or describe what you need… e.g. 'breathable pastel outfit for a daytime wedding under ₹6,000'",
                      label_visibility="collapsed", key="q")
    go = c2.form_submit_button("Search", use_container_width=True, type="primary")
if go and q.strip():
    run_search(q.strip())

st.caption("Try a scenario: Rohan (typo) · Priya (complex) · Ananya (size) · ambiguous · no exact match · lifestyle · skincare · out of scope")
EX = [("Rohan", "wite linnen shirt M"),
      ("Priya", "breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery"),
      ("Ananya", "high-waist straight jeans for office"),
      ("Ambiguous", "outfit for a wedding"),
      ("No match", "chanderi lehenga for a day wedding under ₹6,000"),
      ("Lifestyle", "minimal table lamp for a small reading corner, warm light, under 2500"),
      ("Skincare", "fragrance-free moisturiser for oily acne-prone skin that sits well under sunscreen under 800"),
      ("Order help", "where is my order")]
cols = st.columns(len(EX))
for c, (lbl, ex) in zip(cols, EX):
    if c.button(lbl, use_container_width=True, key="ex" + lbl):
        run_search(ex)
        st.rerun()

# ------------------------------------------------------------------ views
def product_card(p, i=None, checks=None, intent=None):
    with st.container(border=False):
        num = f"#{i} · " if i else ""
        why = f'<div class="why">✦ {html.escape(A.why_this(p, intent))}</div>' if intent else '<div class="why"> </div>'
        ck = ""
        if checks:
            ck = '<div class="chk">' + " ".join(("✓ " if ok else "✕ ") + html.escape(n) for n, ok, _ in checks) + "</div>"
        st.markdown(f'<div class="pcard">{silh(p)}<div class="pbrand">{num}{html.escape(p["brand"])}</div>'
                    f'<div class="pname">{html.escape(p["name"])}</div><div class="price">₹{p["price"]:,}</div>{why}'
                    f'{fit_badge(p)}<br>{risky_note(p)}{ck}</div>', unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        if b1.button("View", key=f"v{p['id']}{i}", use_container_width=True):
            S.pid, S.view = p["id"], "product"; st.rerun()
        if b2.button("Add", key=f"a{p['id']}{i}", use_container_width=True):
            fa = A.fit_agent(p, S.profile)
            size = (fa or {}).get("size") or p["sizes"][min(2, len(p["sizes"]) - 1)]
            S.cart.append(dict(id=p["id"], size=size)); st.toast(f"Added {p['name']} ({size})"); st.rerun()

def grid(items, intent=None):
    cols = st.columns(3)
    for k, it in enumerate(items):
        p, checks = (it if isinstance(it, tuple) else (it, None))
        with cols[k % 3]:
            product_card(p, k + 1, checks, intent)

def view_search():
    res = S.result
    if not res:
        st.info("Type a short query (normal search) or describe what you need in your own words (AI mode). Every product gets a fit check either way.")
        return
    r = res["route"]
    stage = r["stage"] if r["stage"] != "agent" else res.get("intent", {}).get("stage", 1)
    fixes = "".join(f' &nbsp;<small>“{html.escape(a)}” → <b>{html.escape(b)}</b></small>' for a, b in r.get("fixes", []))
    st.markdown(f'<div class="router"><b>Query router</b> (light classifier): {pill(stage)} <small>{html.escape(r["reason"])} · {res["t"]:.1f}s</small>{fixes}</div>',
                unsafe_allow_html=True)

    if res["kind"] == "help":
        st.warning("This looks like an order question, not a product search. Handing you to Help: **My orders → Track order**.")
        return
    if res["kind"] == "keyword":
        if r.get("fixes"):
            u1, u2 = st.columns([3, 2])
            u1.markdown(f"Showing results for **{html.escape(r['query'])}**")
            if u2.button(f"Search instead for “{res['query']}”", key="undo"):
                S.result = dict(res, route=dict(r, fixes=[], stage=0, reason="Undo: original words"), items=[p["id"] for p in A.keyword_search(res["query"])]); st.rerun()
        st.markdown('<div class="layer">LAYER 1 SKIPPED · NORMAL SEARCH · LAYER 2 FIT CHECK STILL ON</div>', unsafe_allow_html=True)
        items = [PRODUCTS[i] for i in res["items"]]
        S.last_results = res["items"]
        grid(items) if items else st.warning("No results. Try describing what you need.")
        return

    intent = res["intent"]
    maps = "".join(f'<div class="map">• “{html.escape(m.get("phrase",""))}” → {html.escape(str(m.get("maps_to","")))}</div>' for m in intent.get("mappings", []) or [])
    st.markdown(f'<div class="aim"><div class="t">✦ AI MODE · HERE\'S WHAT I UNDERSTOOD</div>'
                f'<div class="i">{html.escape(intent.get("interpretation",""))}</div>{maps}</div>', unsafe_allow_html=True)

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
        items, relaxed, _, _ = A.search(it2)

    if relaxed:
        what = ", ".join(f"{k.replace('_',' ')} ({', '.join(v) if isinstance(v, list) else v})" for k, v in relaxed)
        st.markdown(f'<div class="relax">⚖ <b>No exact match.</b> I relaxed: {html.escape(what)}, and kept your budget and other must-haves.</div>', unsafe_allow_html=True)
    S.last_results = [p["id"] for p, _ in items]
    if items:
        st.markdown('<div class="layer">LAYER 1 · VERIFIED RESULTS &nbsp;+&nbsp; LAYER 2 · FIT CHECK</div>', unsafe_allow_html=True)
        grid(items, intent)
    else:
        st.warning("Nothing in the catalog meets your must-haves.")
        if res.get("near"):
            st.caption("Closest options if you can stretch the budget:")
            grid([PRODUCTS[i] for i in res["near"]])

    with st.form("follow", clear_on_submit=True, border=False):
        f1, f2 = st.columns([6, 1])
        fq = f1.text_input("Refine", placeholder="Ask a follow-up… e.g. '#2 but cheaper' or 'same but in lilac'", label_visibility="collapsed")
        if f2.form_submit_button("Refine", use_container_width=True) and fq.strip():
            run_search(fq.strip(), followup=True); st.rerun()

    if show_trace:
        with st.expander("🧠 Agent trace: what SearchSense did", expanded=False):
            st.markdown(f'<div class="step"><b>Router</b> · {html.escape(r["label"])} — {html.escape(r["reason"])}</div>', unsafe_allow_html=True)
            for name, arg, out in res["steps"]:
                st.markdown(f'<div class="step"><b>{html.escape(name)}</b> · <span class="tool">{html.escape(str(arg))}</span><br>{html.escape(str(out))}</div>', unsafe_allow_html=True)
            st.markdown('<div class="step"><b>Fit agent (Layer 2)</b> · size + confidence computed for every result from fit reviews and your profile</div>', unsafe_allow_html=True)
            st.json(intent, expanded=False)

def view_product():
    p = PRODUCTS[S.pid]
    if st.button("← Back to results"):
        S.view = "search"; st.rerun()
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown(silh(p).replace("height:130px", "height:360px"), unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='pbrand'>{p['brand']}</div><h3 style='margin:0'>{html.escape(p['name'])}</h3>"
                    f"<div class='price' style='font-size:22px'>₹{p['price']:,}</div>"
                    f"<div class='why'>{p['fabric'].title()} · {p['colour']} · {', '.join(p['occasions'])} · {p['rating']}★</div>", unsafe_allow_html=True)
        st.markdown('<div class="layer">LAYER 2 · FIT AGENT</div>', unsafe_allow_html=True)
        fa = A.fit_agent(p, S.profile)
        if fa:
            if fa["size"]:
                st.markdown(f'<span class="badge b-{fa["confidence"]}" style="font-size:14px">Recommended: {fa["size"]} · {fa["confidence"]} confidence</span>'
                            f'<div class="why">{html.escape(fa["reason"])}</div>', unsafe_allow_html=True)
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
        else:
            st.caption("Fit check not needed for this product.")
        st.markdown('<div class="layer">HONEST NOTES · FROM REVIEWS</div>', unsafe_allow_html=True)
        for n in p["notes"]:
            st.markdown(f'<span class="note">⚠ {html.escape(n)}</span>', unsafe_allow_html=True)
        st.caption("Reviews: " + " · ".join(f"“{r}”" for r in p["reviews"]))
        rec = (fa or {}).get("size")
        idx = p["sizes"].index(rec) if rec in p["sizes"] else 0
        size = st.radio("Size", p["sizes"], index=idx, horizontal=True)
        if st.button("Add to cart", type="primary"):
            S.cart.append(dict(id=p["id"], size=size)); st.toast("Added to cart"); st.rerun()

def view_cart():
    if st.button("← Back to results"):
        S.view = "search"; st.rerun()
    st.subheader("🛒 Cart")
    if not S.cart:
        st.info("Your cart is empty."); return
    total = 0
    for k, it in enumerate(S.cart):
        p = PRODUCTS[it["id"]]; total += p["price"]
        c1, c2, c3 = st.columns([5, 1, 1])
        c1.markdown(f"**{p['name']}** · size {it['size']}")
        c2.markdown(f"₹{p['price']:,}")
        if c3.button("Remove", key=f"rm{k}"):
            S.cart.pop(k); st.rerun()
    st.markdown(f"**Total: ₹{total:,}**")
    st.markdown('<div class="layer">LAYER 2 · PRE-CHECKOUT RETURN-RISK CHECK</div>', unsafe_allow_html=True)
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

{"search": view_search, "product": view_product, "cart": view_cart}[S.view]()
