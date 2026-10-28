"""SearchSense agent: router, Gemini intent agent, tools, verifier, fit layer."""
import json, re, time, difflib
import requests
from catalog import (PRODUCTS, BREATHABLE, HEAVY, SIZE_ORDER, WAIST_ORDER, ANCHOR_BRANDS,
                     WEATHER, OCCASION_RULES)

# ------------------------------------------------------------------ vocabulary
VOCAB = set()
for p in PRODUCTS.values():
    for f in ("name", "type", "colour", "fabric", "brand", "style", "colour_family", "gender"):
        VOCAB.update(re.findall(r"[a-z]+", str(p[f]).lower()))
VOCAB.update("""for a an the in and or with under below above size sizes men women mens womens
 kurta kurti shirt jeans lehenga saree dress set lamp moisturiser sunscreen jacket white black blue
 green pink yellow red beige ivory pastel cotton linen silk wedding haldi office casual party festive
 that pairs pair jewellery silver gold breathable humid daytime day evening mumbai delhi pune
 under rs inr high waist straight wear outfit ethnic western oily acne prone skin fragrance free sits
 well sunscreen minimal reading corner small warm light lamp table jewelry jewellery something look
 humid breathable daytime pastel sangeet haldi brunch moisturizer moisturiser chanderi""".split())

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
        m = difflib.get_close_matches(t, VOCAB, n=1, cutoff=0.78)
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
    style=["ethnic", "western", "minimal", "boho", "skincare"],
    gender=["women", "men", "unisex"],
    occasion=["wedding", "haldi", "festive", "office", "casual", "party", "brunch", "home", "daily"],
    time=["day", "evening", "any"],
    colour_family=["pastel", "bright", "dark", "neutral"],
    fabrics=sorted({p["fabric"] for p in PRODUCTS.values()}),
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
        if t.split()[0] in q: hard["types"].append(t)
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


def _hard_ok(p, h, drop=()):
    reasons = []
    if h.get("category") and p["category"] != h["category"]: return False, ["category"]
    if h.get("gender") and p["gender"] not in (h["gender"], "unisex"): return False, ["gender"]
    if h.get("budget_max") and p["price"] > h["budget_max"] and "budget" not in drop: return False, ["budget"]
    if h.get("types") and "types" not in drop and p["type"] not in h["types"] and not any(t.split()[0] in p["type"] for t in h["types"]):
        return False, ["type"]
    if h.get("style") and h["style"] in ("ethnic", "western") and p["style"] != h["style"]: return False, ["style"]
    if h.get("size") and p["sizes"] != ["Free"] and h["size"] not in p["sizes"] and "size" not in drop:
        return False, ["size"]
    return True, reasons


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
        blob = (" ".join(p["notes"] + p["reviews"]) + p["name"]).lower()
        ok = {"oily": "oil" in blob or "oily" in blob, "acne": "comedogenic" in blob or "oily" in blob,
              "fragrance-free": "fragrance-free" in blob, "sunscreen": "sunscreen" in blob or "spf" in blob,
              "warm light": "warm" in blob, "small": "small" in blob or "compact" in blob}.get(n, True)
        checks.append((n, ok, ""))
    return checks


RELAX_ORDER = ["pairs", "time", "colour_family", "fabrics", "occasion"]


def search(intent, min_results=2, max_results=6):
    """Catalog search + verifier loop with constraint relaxation."""
    h, s = intent.get("hard", {}), dict(intent.get("soft", {}))
    relaxed, trace = [], []
    for attempt in range(len(RELAX_ORDER) + 1):
        cands = [p for p in PRODUCTS.values() if _hard_ok(p, h)[0]]
        scored = []
        for p in cands:
            checks = check_soft(p, s)
            passed = sum(1 for c in checks if c[1])
            if all(c[1] for c in checks):
                pref = 0.5 if p["colour_family"] in (s.get("prefer_colour_family") or []) else 0
                scored.append((passed + pref + p["rating"] / 10, p, checks))
        scored.sort(key=lambda x: -x[0])
        trace.append(f"Attempt {attempt+1}: {len(cands)} pass hard constraints, {len(scored)} pass all soft checks")
        if len(scored) >= min_results or (relaxed and scored) or attempt == len(RELAX_ORDER):
            break
        # relax the weakest soft constraint that actually unblocks results
        present = [k for k in RELAX_ORDER if s.get(k)]
        if not present:
            break
        pick = present[0]
        for k in present:
            t = dict(s); t[k] = [] if isinstance(t[k], list) else None
            n = sum(1 for p in cands if all(c[1] for c in check_soft(p, t)))
            if n > len(scored):
                pick = k; break
        relaxed.append((pick, s[pick])); s[pick] = [] if isinstance(s[pick], list) else None
        trace.append(f"Verifier: too few matches, relaxed '{pick}' and searched again")
    near = []
    if not scored:  # show near misses on hard constraints, e.g. over budget
        for p in PRODUCTS.values():
            ok, why = _hard_ok(p, h, drop=("budget",))
            if ok: near.append(p)
    return [(p, c) for _, p, c in scored[:max_results]], relaxed, trace, near[:3]


def keyword_search(query, max_results=8):
    toks = [t for t in re.findall(r"[a-z]+", query.lower()) if len(t) > 1]
    size = SIZE_RE.search(query)
    res = []
    for p in PRODUCTS.values():
        blob = f"{p['name']} {p['type']} {p['colour']} {p['fabric']} {p['gender']}".lower()
        hits = sum(1 for t in toks if t in blob)
        if hits and (not size or size.group(1).upper() in p["sizes"] or p["sizes"] == ["Free"]):
            res.append((hits + p["rating"] / 10, p))
    res.sort(key=lambda x: -x[0])
    return [p for _, p in res[:max_results]]


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
    return "; ".join(bits[:3]) or f"{p['rating']}★ {p['type']}"


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
    return dict(size=rec, confidence=conf, reason=reason, ask=ask)


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
