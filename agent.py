"""SearchSense agent: router, Gemini intent agent, tools, verifier, fit layer."""
import json, re, time, difflib, zlib, collections
import numpy as np
import requests
from catalog import (PRODUCTS, BREATHABLE, HEAVY, SIZE_ORDER, WAIST_ORDER, ANCHOR_BRANDS,
                     WEATHER, OCCASION_RULES)

# ------------------------------------------------------------------ vocabulary
_FIELDS = ("name", "type", "colour", "fabric", "brand", "style", "colour_family", "gender")
_TOKEN_FREQ = collections.Counter()
_DEMO_TOKENS = set()
for p in PRODUCTS.values():
    toks = {w for f in _FIELDS for w in re.findall(r"[a-z]+", str(p[f]).lower())}
    _TOKEN_FREQ.update(toks)
    if p.get("source") == "demo":
        _DEMO_TOKENS |= toks
# words from the data must appear on >= 3 products (or be demo words), so one-off brand fragments aren't "correct" spellings
_STATIC_VOCAB = _DEMO_TOKENS | set("""for a an the in and or with under below above size sizes men women mens womens
 kurta kurti shirt jeans lehenga saree dress set lamp moisturiser sunscreen jacket white black blue
 green pink yellow red beige ivory pastel cotton linen silk wedding haldi office casual party festive
 that pairs pair jewellery silver gold breathable humid daytime day evening mumbai delhi pune
 under rs inr high waist straight wear outfit ethnic western oily acne prone skin fragrance free sits
 well sunscreen minimal reading corner small warm light lamp table jewelry jewellery something look
 humid breathable daytime pastel sangeet haldi brunch moisturizer moisturiser chanderi""".split())   # hand-written words win spelling ties
VOCAB = {w for w, n in _TOKEN_FREQ.items() if n >= 3} | _STATIC_VOCAB
# spelling candidates are bucketed by first letter so correction stays fast with thousands of words
_VOCAB_BY_FIRST = collections.defaultdict(list)
for _w in VOCAB:
    _VOCAB_BY_FIRST[_w[0]].append(_w)

SUBJECTIVE = {"breathable", "humid", "pairs", "pair", "jewellery", "occasion", "wedding", "haldi", "sangeet",
              "daytime", "evening", "office", "party", "festive", "brunch", "minimal", "cosy", "cozy", "warm",
              "oily", "acne", "dry", "sensitive", "fragrance", "comfortable", "light", "heavy", "elegant",
              "something", "outfit", "look", "vibe", "goes", "match", "matches", "suits", "under", "budget"}
OUT_OF_SCOPE = re.compile(r"\b(where is my order|track|refund|cancel|return my|my order|exchange my|delivery status|customer care)\b")
SIZE_RE = re.compile(r"\b(xs|s|m|l|xl|xxl|2[68]|3[0246])\b", re.I)


def correct_tokens(q):
    """Light spelling correction against catalog vocabulary (stage 2)."""
    out, fixes = [], []
    for tok in q.split():
        t = tok.lower()
        if len(t) <= 2 or t in VOCAB or not t.isalpha():
            out.append(tok); continue
        m = difflib.get_close_matches(t, _VOCAB_BY_FIRST.get(t[0], []), n=6, cutoff=0.78)
        # best similarity first; among near-equal candidates prefer the commoner word ("wite" -> white, not write)
        m = sorted(m, key=lambda w: (-round(difflib.SequenceMatcher(None, t, w).ratio(), 2), -_TOKEN_FREQ[w] - 10**6 * (w in _STATIC_VOCAB)))
        if m and m[0] != t:
            out.append(m[0]); fixes.append((tok, m[0]))
        else:
            out.append(tok)
    return " ".join(out), fixes


def route(query):
    """Light classifier: decides stage 0 / 2 / 6 locally, or hands complex queries to the agent."""
    q = query.strip()
    ql = q.lower()
    if OUT_OF_SCOPE.search(ql):
        return dict(stage=6, label="Out of scope", reason="Order or returns question, not a product search")
    corrected, fixes = correct_tokens(q)
    toks = re.findall(r"[a-z₹0-9]+", corrected.lower())
    subj = [t for t in toks if t in SUBJECTIVE]
    complex_q = len(toks) >= 6 or len(subj) >= 1 or bool(re.search(r"₹|\brs\b|\d{3,}", ql))
    if complex_q:
        return dict(stage="agent", label="Complex query: sent to agent", query=q, fixes=[],
                    reason=f"{len(toks)} words; subjective/context words: {', '.join(subj) or 'budget'}")
    if fixes:
        return dict(stage=2, label="Minor correction", query=corrected, fixes=fixes,
                    reason="Spelling fixed silently; meaning not in doubt")
    return dict(stage=0, label="Pass-through", query=q, fixes=[], reason="Short, specific query: normal search")


# ------------------------------------------------------------------ Gemini
ALLOWED = dict(
    category=["fashion", "lifestyle", "personal care"],
    style=["ethnic", "western", "minimal", "boho", "skincare", "beauty"],
    gender=["women", "men", "unisex"],
    occasion=["wedding", "haldi", "festive", "office", "casual", "party", "brunch", "home", "daily"],
    time=["day", "evening", "any"],
    colour_family=["pastel", "bright", "dark", "neutral"],
    fabrics=sorted({p["fabric"] for p in PRODUCTS.values() if p["fabric"]}),
    types=sorted({p["type"] for p in PRODUCTS.values()}),
    pairs=["silver", "gold", "any"],
)

SYSTEM = f"""You are the intent agent inside SearchSense, an AI mode in an Indian e-commerce search bar
(fashion, lifestyle, personal care). Turn the shopper's query into structured constraints for catalog search.
Return ONLY JSON with this schema:
{{"stage": 1|3|4|5,
  "interpretation": "one short line describing what the shopper wants",
  "hard": {{"category": str|null, "gender": str|null, "budget_max": int|null, "size": str|null, "types": [str], "style": str|null}},
  "soft": {{"occasion": str|null, "time": str|null, "city": str|null, "colour_family": [str], "colours": [str], "fabrics": [str], "pairs": str|null, "needs": [str]}},
  "mappings": [{{"phrase": "words the shopper used", "maps_to": "catalog attributes you mapped them to"}}],
  "clarify": null | {{"question": str, "options": [str, str, str]}}
}}
Stages: 1 = clear intent (constraints explicit); 3 = major semantic (subjective words you mapped to attributes);
4 = ambiguous (a missing detail would split results heavily, e.g. ethnic vs western, day vs evening). Ask ONE question only
at stage 4, with 2-4 short tappable options. Do not ask if a reasonable default exists.
Allowed values: category {ALLOWED['category']}; style {ALLOWED['style']}; gender {ALLOWED['gender']};
occasion {ALLOWED['occasion']}; time {ALLOWED['time']}; colour_family {ALLOWED['colour_family']};
fabrics {ALLOWED['fabrics']}; types {ALLOWED['types']}; pairs {ALLOWED['pairs']}.
If gender is not stated, infer it only from clear words (lehenga, saree, anarkali -> women); otherwise null.
Rules: "breathable"/"humid"/"summer" -> fabrics cotton, linen, chanderi, mul cotton, cotton-silk.
"pairs with silver jewellery" -> pairs "silver". Rupee amounts -> budget_max. Only use allowed values; leave unknowns null/empty.
For personal care, put skin needs (oily, acne-prone, fragrance-free, under sunscreen) in soft.needs."""


def call_gemini(api_key, model, query, history=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    convo = ""
    if history:
        convo = "Earlier in this search session: " + " | ".join(history[-3:]) + "\nNow the shopper says: "
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": convo + query}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    r = requests.post(url, json=body, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(txt)


def rule_parse(query, history=None):
    """Offline fallback parser, used only if Gemini is unavailable."""
    q = query.lower()
    if history:
        q = " ".join(history[-2:]).lower() + " " + q
    hard = dict(category=None, gender=None, budget_max=None, size=None, types=[], style=None)
    soft = dict(occasion=None, time=None, city=None, colour_family=[], colours=[], fabrics=[], pairs=None, needs=[])
    maps = []
    m = re.findall(r"(?:₹|rs\.?\s?|under\s)(\d[\d,]*)", q)
    if m: hard["budget_max"] = int(m[-1].replace(",", ""))
    if any(w in q for w in ["lamp", "cushion", "decor"]): hard["category"] = "lifestyle"
    elif any(w in q for w in ["moisturiser", "moisturizer", "sunscreen", "skin", "cream"]): hard["category"] = "personal care"
    else: hard["category"] = "fashion"
    if re.search(r"\b(men|mens|man|him)\b", q): hard["gender"] = "men"
    elif re.search(r"\b(women|womens|her|she)\b", q) or any(w in q for w in ["lehenga", "saree", "anarkali", "sharara", "dress"]): hard["gender"] = "women"
    for t in ALLOWED["types"]:
        if re.search(rf"\b{re.escape(t)}s?\b", q): hard["types"].append(t)
    if not hard["types"]:  # "anarkali" -> "anarkali set": a first word that identifies exactly one type
        first = collections.Counter(t.split()[0] for t in ALLOWED["types"])
        hard["types"] = [t for t in ALLOWED["types"] if first[t.split()[0]] == 1 and re.search(rf"\b{re.escape(t.split()[0])}s?\b", q)]
    if "ethnic" in q or any(w in q for w in ["kurta", "lehenga", "saree", "anarkali"]): hard["style"] = "ethnic"
    elif "western" in q or "jeans" in q or "dress" in q: hard["style"] = "western"
    for o in ALLOWED["occasion"]:
        if o in q: soft["occasion"] = o
    if "daytime" in q or "day " in q or "morning" in q: soft["time"] = "day"
    if "evening" in q or "night" in q: soft["time"] = "evening"
    for c in WEATHER:
        if c in q: soft["city"] = c
    for cf in ALLOWED["colour_family"]:
        if cf in q: soft["colour_family"].append(cf)
    for f in ALLOWED["fabrics"]:
        if f in q: soft["fabrics"].append(f)
    if "breathable" in q or "humid" in q:
        soft["fabrics"] = sorted(set(soft["fabrics"]) | {"cotton", "linen", "chanderi", "mul cotton"})
        maps.append(dict(phrase="breathable / humid", maps_to="cotton, linen, chanderi, mul cotton"))
    if "silver" in q: soft["pairs"] = "silver"; maps.append(dict(phrase="pairs with silver", maps_to="silver-friendly colours & trims"))
    if "gold" in q: soft["pairs"] = "gold"
    for n in ["oily", "acne", "fragrance-free", "sunscreen", "warm light", "small"]:
        if n in q: soft["needs"].append(n)
    m2 = SIZE_RE.search(query)
    if m2: hard["size"] = m2.group(1).upper()
    stage = 3 if maps else 1
    clarify = None
    if hard["category"] == "fashion" and soft["occasion"] == "wedding" and not hard["style"] and not hard["types"]:
        stage, clarify = 4, dict(question="Ethnic or western for the wedding?", options=["Ethnic", "Western", "Show both"])
    return dict(stage=stage, interpretation="Parsed with offline rules (Gemini unavailable)", hard=hard, soft=soft,
                mappings=maps, clarify=clarify)


def understand(query, api_key, models, history=None):
    """Run the intent agent with model fallback; returns (intent, model_used, log)."""
    log = []
    if api_key:
        for model in models:
            t0 = time.time()
            try:
                out = call_gemini(api_key, model, query, history)
                log.append(f"{model}: ok in {time.time()-t0:.1f}s")
                return out, model, log
            except Exception as e:
                log.append(f"{model}: {str(e)[:90]}")
    else:
        log.append("No GEMINI_API_KEY set")
    return rule_parse(query, history), "offline rules", log


# ------------------------------------------------------------------ tools
def weather_tool(city):
    return WEATHER.get((city or "").lower())


def occasion_tool(occasion, time_):
    if not occasion: return None
    return OCCASION_RULES.get((occasion, time_ or "day"))


def enrich(intent):
    """Context tools: weather + occasion rules add soft preferences."""
    soft = intent.setdefault("soft", {})
    calls = []
    w = weather_tool(soft.get("city"))
    if soft.get("city"):
        calls.append(("weather_tool", f"city={soft['city']}", f"{w['note']}, {w['temp']}" if w else "no data"))
    if w and w["climate"] == "humid":
        soft["fabrics"] = sorted(set(soft.get("fabrics") or []) | BREATHABLE)
    occ = occasion_tool(soft.get("occasion"), soft.get("time"))
    if soft.get("occasion"):
        calls.append(("occasion_rules", f"{soft.get('occasion')}, {soft.get('time') or 'day'}", occ["tip"] if occ else "no rule"))
    if occ:
        soft["prefer_colour_family"] = occ["colour_family"]
    return intent, calls


def _type_match(h_types, ptype):
    """Hard type filter: exact type, or the filter's head word is a whole word of the product type ('kurta' ~ 'kurta set')."""
    words = ptype.split()
    return ptype in h_types or any(t.split()[0] in words for t in h_types)


def _hard_ok(p, h, drop=()):
    """Per-product hard-constraint check (reference implementation; search() uses the vectorised masks below)."""
    reasons = []
    if h.get("category") and p["category"] != h["category"]: return False, ["category"]
    if h.get("gender") and p["gender"] not in (h["gender"], "unisex"): return False, ["gender"]
    if h.get("budget_max") and p["price"] > h["budget_max"] and "budget" not in drop: return False, ["budget"]
    if h.get("types") and "types" not in drop and not _type_match(h["types"], p["type"]):
        return False, ["type"]
    if h.get("style") and h["style"] in ("ethnic", "western") and p["style"] != h["style"]: return False, ["style"]
    if h.get("size") and p["sizes"] != ["Free"] and h["size"] not in p["sizes"] and "size" not in drop:
        return False, ["size"]
    return True, reasons


def _need_ok(p, n):
    blob = (" ".join(p["notes"] + p["reviews"]) + p["name"]).lower()
    return {"oily": "oil" in blob or "oily" in blob, "acne": "comedogenic" in blob or "oily" in blob,
            "fragrance-free": "fragrance-free" in blob, "sunscreen": "sunscreen" in blob or "spf" in blob,
            "warm light": "warm" in blob, "small": "small" in blob or "compact" in blob}.get(n, True)


def check_soft(p, s):
    """Verifier: per-constraint pass/fail for a product."""
    checks = []
    if s.get("fabrics"):
        checks.append(("fabric", p["fabric"] in s["fabrics"], p["fabric"]))
    if s.get("colour_family"):
        checks.append(("colour", p["colour_family"] in s["colour_family"], p["colour"]))
    if s.get("occasion") and s["occasion"] not in ("home", "daily"):
        checks.append(("occasion", s["occasion"] in p["occasions"], "/".join(p["occasions"][:2])))
    if s.get("time") and s["time"] != "any":
        checks.append(("time", p["time"] in (s["time"], "any"), p["time"]))
    if s.get("pairs") and s["pairs"] != "any":
        checks.append(("pairs with " + s["pairs"], p["pairs"] in (s["pairs"], "any"), p["pairs"]))
    for n in s.get("needs") or []:
        checks.append((n, _need_ok(p, n), ""))
    return checks


# ------------------------------------------------------------------ indices (built once at import)
# Everything the search loop needs is turned into integer / boolean numpy arrays, so a query over thousands of
# products costs a few vector operations instead of a Python loop per product.
_PL = list(PRODUCTS.values())            # position -> product
_N = len(_PL)


def _coded(field):
    vals = [p[field] for p in _PL]
    m = {v: i for i, v in enumerate(sorted(set(vals)))}
    return np.array([m[v] for v in vals], dtype=np.int32), m


_CAT, _CAT_M = _coded("category")
_GEN, _GEN_M = _coded("gender")
_STY, _STY_M = _coded("style")
_TYP, _TYP_M = _coded("type")
_FAB, _FAB_M = _coded("fabric")
_CFAM, _CFAM_M = _coded("colour_family")
_TIME, _TIME_M = _coded("time")
_PAIR, _PAIR_M = _coded("pairs")
_BRAND, _ = _coded("brand")
_PRICE = np.array([p["price"] for p in _PL], dtype=np.int64)
# rated products rank above unrated ones (the Myntra data has no ratings); the jitter is a stable tie-break
_RATING = np.array([(p.get("rating") or 0) / 10 for p in _PL])
_JITTER = np.array([zlib.crc32(p["id"].encode()) / 2**32 * 0.05 for p in _PL])
_FREE = np.array([p["sizes"] == ["Free"] for p in _PL])
_SIZE_M = {}
_OCC_M = {}
for _i, _p in enumerate(_PL):
    for _sz in _p["sizes"]:
        _SIZE_M.setdefault(_sz.upper(), np.zeros(_N, bool))[_i] = True
    for _o in _p["occasions"]:
        _OCC_M.setdefault(_o, np.zeros(_N, bool))[_i] = True
_NEED_M = {}
_ZERO = np.zeros(_N, bool)


def _isin(codes, mapping, values):
    ids = [mapping[v] for v in values if v in mapping]
    return np.isin(codes, ids) if ids else _ZERO


def _hard_mask(h, drop=()):
    m = np.ones(_N, bool)
    if h.get("category"): m &= _CAT == _CAT_M.get(h["category"], -1)
    if h.get("gender"): m &= (_GEN == _GEN_M.get(h["gender"], -1)) | (_GEN == _GEN_M.get("unisex", -1))
    if h.get("budget_max") and "budget" not in drop: m &= _PRICE <= h["budget_max"]
    if h.get("types") and "types" not in drop:
        m &= _isin(_TYP, _TYP_M, [t for t in _TYP_M if _type_match(h["types"], t)])
    if h.get("style") in ("ethnic", "western"): m &= _STY == _STY_M.get(h["style"], -1)
    if h.get("size") and "size" not in drop: m &= _FREE | _SIZE_M.get(str(h["size"]).upper(), _ZERO)
    return m


def _soft_masks(s):
    """One boolean array per active soft constraint (same semantics as check_soft)."""
    out = []
    if s.get("fabrics"): out.append(_isin(_FAB, _FAB_M, s["fabrics"]))
    if s.get("colour_family"): out.append(_isin(_CFAM, _CFAM_M, s["colour_family"]))
    if s.get("occasion") and s["occasion"] not in ("home", "daily"): out.append(_OCC_M.get(s["occasion"], _ZERO))
    if s.get("time") and s["time"] != "any": out.append(_isin(_TIME, _TIME_M, [s["time"], "any"]))
    if s.get("pairs") and s["pairs"] != "any": out.append(_isin(_PAIR, _PAIR_M, [s["pairs"], "any"]))
    for n in s.get("needs") or []:
        if n not in _NEED_M: _NEED_M[n] = np.array([_need_ok(p, n) for p in _PL])
        out.append(_NEED_M[n])
    return out


def _all(masks, base):
    m = base.copy()
    for x in masks: m &= x
    return m


def _top(idx, score, k, per_brand):
    """Best k positions by score, at most per_brand per brand (relaxed if that leaves fewer than k)."""
    if not len(idx): return []
    order = idx[np.argsort(-score[idx], kind="stable")]
    picked, count, spill = [], collections.Counter(), []
    for i in order:
        if count[_BRAND[i]] < per_brand:
            picked.append(i); count[_BRAND[i]] += 1
            if len(picked) == k: break
        else:
            spill.append(i)
    return picked + spill[:k - len(picked)]


RELAX_ORDER = ["pairs", "time", "colour_family", "fabrics", "occasion"]


def search(intent, min_results=2, max_results=6):
    """Catalog search + verifier loop with constraint relaxation."""
    h, s = intent.get("hard", {}), dict(intent.get("soft", {}))
    relaxed, trace = [], []
    base = _hard_mask(h)
    prefer = _isin(_CFAM, _CFAM_M, s.get("prefer_colour_family") or [])
    for attempt in range(len(RELAX_ORDER) + 1):
        ok = _all(_soft_masks(s), base)
        n_scored = int(ok.sum())
        trace.append(f"Attempt {attempt+1}: {int(base.sum()):,} pass hard constraints, {n_scored:,} pass all soft checks")
        if n_scored >= min_results or (relaxed and n_scored) or attempt == len(RELAX_ORDER):
            break
        # relax the weakest soft constraint that actually unblocks results
        present = [k for k in RELAX_ORDER if s.get(k)]
        if not present:
            break
        pick = present[0]
        for k in present:
            t = dict(s); t[k] = [] if isinstance(t[k], list) else None
            if int(_all(_soft_masks(t), base).sum()) > n_scored:
                pick = k; break
        relaxed.append((pick, s[pick])); s[pick] = [] if isinstance(s[pick], list) else None
        trace.append(f"Verifier: too few matches, relaxed '{pick}' and searched again")
    score = _RATING + prefer * 0.5 + _JITTER
    chosen = _top(np.flatnonzero(ok), score, max_results, per_brand=2)
    near = []
    if not len(chosen):  # show near misses on hard constraints, e.g. over budget: the cheapest few
        idx = np.flatnonzero(_hard_mask(h, drop=("budget",)))
        near = [_PL[i] for i in idx[np.argsort(_PRICE[idx], kind="stable")][:3]]
    return [(_PL[i], check_soft(_PL[i], s)) for i in chosen], relaxed, trace, near


def _kw_stem(t):
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


_KW_INDEX = collections.defaultdict(list)
for _i, _p in enumerate(_PL):
    for _t in {_kw_stem(w) for w in re.findall(r"[a-z]+", f"{_p['name']} {_p['type']} {_p['colour']} {_p['fabric']} {_p['gender']}".lower())}:
        _KW_INDEX[_t].append(_i)
_KW_INDEX = {t: np.array(v, dtype=np.int64) for t, v in _KW_INDEX.items()}


def keyword_search(query, max_results=8):
    toks = {_kw_stem(t) for t in re.findall(r"[a-z]+", query.lower()) if len(t) > 1}
    size = SIZE_RE.search(query)
    hits = np.zeros(_N)
    for t in toks:
        if t in _KW_INDEX: hits[_KW_INDEX[t]] += 1
    ok = hits > 0
    if size: ok &= _FREE | _SIZE_M.get(size.group(1).upper(), _ZERO)
    return [_PL[i] for i in _top(np.flatnonzero(ok), hits + _RATING + _JITTER, max_results, per_brand=3)]


def why_this(p, intent):
    s = intent.get("soft", {})
    bits = []
    if p["fabric"] in BREATHABLE and (s.get("fabrics") or s.get("city")):
        bits.append(f"breathable {p['fabric']}")
    if s.get("colour_family") and p["colour_family"] in s["colour_family"]:
        bits.append(f"{p['colour']} suits {s.get('time') or 'the'} {s.get('occasion') or 'look'}".replace("the look", "the look"))
    if s.get("pairs") == "silver" and p["pairs"] in ("silver", "any"):
        bits.append("works with silver")
    h = intent.get("hard", {})
    if h.get("budget_max"):
        bits.append(f"₹{h['budget_max'] - p['price']:,} under budget" if p["price"] <= h["budget_max"] else "over budget")
    for n in s.get("needs") or []:
        bits.append(n.replace("-", " "))
    return "; ".join(bits[:3]) or (f"{p['rating']}★ {p['type']}" if p.get("rating") else " · ".join(x for x in (p["type"], p["colour"]) if x))


# ------------------------------------------------------------------ Layer 2: fit agent
def _scale(p):
    return WAIST_ORDER if p["sizes"][0].isdigit() else SIZE_ORDER


def fit_agent(p, profile):
    """Size recommendation with confidence. profile: usual_size, anchor_brand, anchor_size, past_brands."""
    if p["category"] != "fashion" or p["sizes"] == ["Free"]:
        return None
    scale = _scale(p)
    base = profile.get("anchor_size") or profile.get("usual_size")
    if p["sizes"][0].isdigit():
        base = profile.get("waist") or None
    if not base or base not in scale:
        return dict(size=None, confidence="low", reason="No size history or anchor for you yet",
                    ask="Which brand fits you best, and in what size?")
    idx = scale.index(base)
    offset = ANCHOR_BRANDS.get(profile.get("anchor_brand") or "", 0) or 0
    adj = -p["fit_signal"]  # runs small (-1) -> size up (+1)
    rec_idx = max(0, min(len(scale) - 1, idx + offset + adj))
    rec = scale[rec_idx]
    has_anchor = bool(profile.get("anchor_brand") and profile.get("anchor_brand") != "None / not sure") or p["brand"] in profile.get("past_brands", [])
    if p["brand"] in profile.get("past_brands", []) and p["fit_reviews"] >= 20:
        conf = "high"
    elif p["fit_reviews"] >= 40 and has_anchor:
        conf = "high"
    elif p["fit_reviews"] >= 20 or has_anchor:
        conf = "medium"
    else:
        conf = "low"
    signal = {-1: "runs small", 0: "true to size", 1: "runs large"}[p["fit_signal"]]
    reason = f"{p['fit_reviews']} reviews mention fit: {signal}"
    if rec != base: reason += f", so {('size up' if rec_idx > idx else 'size down')} from {base}"
    ask = "Which brand fits you best, and in what size?" if conf == "low" else None
    if rec not in p["sizes"]:
        return dict(size=None, confidence="low", reason=f"Your likely size {rec} is not stocked", ask=None)
    return dict(size=rec, confidence=conf, reason=reason, ask=ask, simulated=bool(p.get("fit_sim")))


def precheckout(cart, profile):
    """Return-risk check across the cart: bracketing + size mismatch + honest notes."""
    risks = []
    seen = {}
    for item in cart:
        seen.setdefault(item["id"], []).append(item["size"])
    for pid, sizes in seen.items():
        p = PRODUCTS[pid]
        if len(sizes) > 1:
            fa = fit_agent(p, profile)
            keep = fa["size"] if fa and fa["size"] in sizes else sizes[0]
            risks.append(dict(level="high", pid=pid, kind="bracketing",
                              msg=f"Two sizes of {p['name']} ({', '.join(sizes)}). Our fit check suggests keeping {keep}; one of these is likely to come back.",
                              fix=("keep", keep)))
        else:
            fa = fit_agent(p, profile)
            if fa and fa["size"] and fa["size"] != sizes[0]:
                risks.append(dict(level="medium", pid=pid, kind="size",
                                  msg=f"{p['name']}: you picked {sizes[0]}, but {fa['reason'].split(':')[-1].strip()}. Switch to {fa['size']}?",
                                  fix=("switch", fa["size"])))
        for n in p["notes"]:
            if any(w in n.lower() for w in ["sheer", "see-through", "peach", "heavy", "creases", "fragrance", "not included", "cool white"]):
                risks.append(dict(level="info", pid=pid, kind="note", msg=f"{p['name']}: {n}", fix=None))
    return risks
