"""SearchSense agent: router, Gemini intent agent, tools, verifier, fit layer."""
import json, re, time, difflib, zlib, collections
import numpy as np
import requests
from catalog import (PRODUCTS, BREATHABLE, HEAVY, SIZE_ORDER, WAIST_ORDER, ANCHOR_BRANDS,
                     WEATHER, OCCASION_RULES)
from prompt import NEEDS, build_system_prompt, build_response_schema

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
 humid breathable daytime pastel sangeet haldi brunch moisturizer moisturiser chanderi
 gym running run workout yoga sports sport training jogging trek trekking hiking travel beach swimming cycling""".split())   # hand-written words win spelling ties
VOCAB = {w for w, n in _TOKEN_FREQ.items() if n >= 3} | _STATIC_VOCAB
# spelling candidates are bucketed by first letter so correction stays fast with thousands of words
_VOCAB_BY_FIRST = collections.defaultdict(list)
for _w in VOCAB:
    if len(_w) >= 3:   # never "correct" into a unit or fragment like "gm"
        _VOCAB_BY_FIRST[_w[0]].append(_w)

SUBJECTIVE = {"breathable", "humid", "pairs", "pair", "jewellery", "occasion", "wedding", "haldi", "sangeet",
              "daytime", "evening", "office", "party", "festive", "brunch", "minimal", "cosy", "cozy", "warm",
              "oily", "acne", "dry", "sensitive", "fragrance", "comfortable", "light", "heavy", "elegant",
              "something", "outfit", "look", "vibe", "goes", "match", "matches", "suits", "under", "budget",
              # activities and purposes change what a good product is (gym -> quick-dry fabric), so they go to the agent
              "gym", "running", "run", "workout", "yoga", "sports", "sport", "training", "jogging", "trek", "trekking",
              "hiking", "travel", "beach", "swimming", "cycling", "winter", "summer", "rainy", "monsoon", "gift"}
_PURPOSE_RE = re.compile(r"\bfor\s+(?!(?:men|women|mens|womens|him|her|boys|girls|kids|unisex)\b)[a-z]")
# Customer-support requests (orders, returns, payments, account): not product searches, so they go to Help, not the catalog.
OUT_OF_SCOPE = re.compile(
    r"\b(refunds?|returns?|returning|cancel(?:led|lation)?|exchange|replace(?:ment)?)\b.*\b(order|item|product|it|this|parcel|package)\b"
    r"|\b(order|item|parcel|package)\b.*\b(returns?|refunds?|cancel|exchange|status|track|tracking|delayed|late|missing|damaged|wrong)\b"
    r"|\b(where is my|my orders?|order status|order id|delivery status|not (?:yet )?delivered|out for delivery|shipment|courier)\b"
    r"|\btrack(?:ing)?\b(?!\s*(?:pants?|suits?|jackets?|tops?))"
    r"|\b(refund|return policy|customer (?:care|service|support)|help ?desk|help chat|contact us|talk to (?:an? )?(?:agent|human|person)|complaint|"
    r"invoice|payment (?:failed|issue|problem|pending)|money (?:back|deducted)|coupon (?:not|isn)|promo code|my account|log ?in|password|"
    r"change (?:my )?(?:address|phone|number)|cash on delivery|cod)\b")
SIZE_RE = re.compile(r"(?<!['’])\b(xs|s|m|l|xl|xxl|2[68]|3[0246])\b", re.I)   # not the "s" in "sister's"


# Spelling variants that are too far from the catalog word for fuzzy matching ("sari" vs "saree" is only 67% similar)
ALIASES = {"sari": "saree", "saris": "sarees", "sarree": "saree", "lengha": "lehenga", "lehnga": "lehenga", "lahenga": "lehenga",
           "ghagra": "lehenga", "kurtha": "kurta", "kurthi": "kurti", "kurtis": "kurti", "shalwar": "salwar",
           "chudidar": "churidar", "dupata": "dupatta", "duppata": "dupatta", "sherwaani": "sherwani", "pajama": "pyjama",
           "pajamas": "pyjama", "tshirt": "t-shirt", "tshirts": "t-shirt", "tees": "t-shirt", "jean": "jeans", "denims": "jeans",
           "trouser": "trousers", "pant": "pants", "moisturizer": "moisturiser", "jewelry": "jewellery",
           "lipstik": "lipstick", "parfum": "perfume", "kurtaset": "kurta set", "coord": "co-ord", "cushions": "cushion"}


def correct_tokens(q):
    """Light spelling correction against catalog vocabulary (stage 2)."""
    out, fixes = [], []
    for tok in q.split():
        t = tok.lower()
        if t in ALIASES and ALIASES[t] != t:
            out.append(ALIASES[t]); fixes.append((tok, ALIASES[t])); continue
        if len(t) <= 3 or t in VOCAB or not t.isalpha():   # 3-letter words ("gym") are too short to correct safely
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
    purpose = _PURPOSE_RE.search(corrected.lower())
    words = [t for t in re.findall(r"[a-z]+", corrected.lower()) if len(t) > 2]
    if not SIZE_RE.fullmatch(q) and (not words or not any(t in VOCAB or _kw_stem(t) in VOCAB for t in words)):   # "hi", "iphone"
        return dict(stage="agent", label="Unfamiliar words: sent to agent", query=q, fixes=[],
                    reason="None of these words appear in the catalog, so the agent decides what the shopper wants")
    complex_q = len(toks) >= 6 or len(subj) >= 1 or bool(purpose) or bool(re.search(r"₹|\brs\b|\d{3,}", ql))
    if complex_q:
        why = ", ".join(subj) or (f"purpose “{purpose.group(0)}…”" if purpose else "budget")
        return dict(stage="agent", label="Complex query: sent to agent", query=q, fixes=[],
                    reason=f"{len(toks)} words; subjective/context words: {why}")
    if fixes:
        return dict(stage=2, label="Minor correction", query=corrected, fixes=fixes,
                    reason="Spelling fixed silently; meaning not in doubt")
    return dict(stage=0, label="Pass-through", query=q, fixes=[], reason="Short, specific query: normal search")


# ------------------------------------------------------------------ Gemini
ALLOWED = dict(
    category=["fashion", "lifestyle", "personal care"],
    style=["ethnic", "western", "minimal", "boho", "skincare", "beauty"],
    gender=["women", "men", "unisex"],
    occasion=["wedding", "haldi", "festive", "office", "casual", "party", "brunch", "sports", "home", "daily"],
    time=["day", "evening", "any"],
    colour_family=["pastel", "bright", "dark", "neutral"],
    fabrics=sorted({p["fabric"] for p in PRODUCTS.values() if p["fabric"]}),
    types=sorted({p["type"] for p in PRODUCTS.values()}),
    pairs=["silver", "gold", "any"],
    needs=list(NEEDS),
)
TYPES_BY_CATEGORY = {c: sorted({p["type"] for p in PRODUCTS.values() if p["category"] == c}) for c in ALLOWED["category"]}

# Colour words in the catalog, and what a requested colour may match ("lilac" also accepts lavender and mauve)
_COLOUR_MODIFIERS = {"and", "light", "dark", "mid", "floral", "clear", "pastel", "multi", "multicoloured", "multicolour", "natural",
                     "sky", "powder", "baby", "off", "skin", "bottle", "forest", "army", "sea", "hot", "neon", "parrot", "peacock", "ice"}
# every colour phrase in the catalog ("sky blue", "navy blue", "lilac"), split on "&"
COLOUR_PHRASES = sorted({c.strip() for p in PRODUCTS.values() for c in p["colour"].split("&") if c.strip()} - _COLOUR_MODIFIERS)
COLOUR_WORDS = sorted({w for c in COLOUR_PHRASES for w in c.split()} - _COLOUR_MODIFIERS)
COLOUR_SYNONYMS = {
    "lilac": ["lilac", "lavender", "mauve"], "lavender": ["lavender", "lilac", "mauve"], "purple": ["purple", "violet", "lilac", "lavender", "plum"],
    "pink": ["pink", "blush", "rose", "fuchsia"], "red": ["red", "maroon", "wine"], "maroon": ["maroon", "burgundy", "wine"],
    "blue": ["blue", "navy", "indigo"], "navy": ["navy"], "green": ["green", "mint", "olive", "sage", "emerald", "sea"],
    "white": ["white", "off-white", "ivory", "cream"], "off-white": ["off-white", "ivory", "cream"], "ivory": ["ivory", "off-white", "cream"],
    "cream": ["cream", "ivory", "off-white", "beige"], "beige": ["beige", "cream", "nude", "khaki", "tan"],
    "yellow": ["yellow", "mustard", "lemon"], "grey": ["grey", "gray", "charcoal", "silver"], "gray": ["grey", "gray", "charcoal"],
    "brown": ["brown", "tan", "coffee", "rust", "camel"], "orange": ["orange", "rust", "coral"], "gold": ["gold", "golden"],
}



def colour_targets(colour):
    """What a requested colour may match: its own phrase, plus close shades of its head colour ("navy blue" -> navy)."""
    words = colour.split()
    if len(words) == 1:
        return COLOUR_SYNONYMS.get(colour, [colour])
    return [colour] + COLOUR_SYNONYMS.get(words[0], [])


SYSTEM = build_system_prompt(ALLOWED, TYPES_BY_CATEGORY, sorted(set(COLOUR_WORDS) | set(COLOUR_SYNONYMS)))
RESPONSE_SCHEMA = build_response_schema(ALLOWED)


def _compact_previous(prev):
    """Previous search's constraints, without empty fields, for follow-ups."""
    if not prev: return ""
    out = {}
    for sec in ("hard", "soft"):
        d = {k: v for k, v in (prev.get(sec) or {}).items() if v not in (None, [], "", False) and k != "prefer_colour_family"}
        if d: out[sec] = d
    return f"[Previous search constraints: {json.dumps(out, ensure_ascii=False)}] " if out else ""


def call_gemini(api_key, model, query, history=None, previous=None, use_schema=True):
    """One Gemini call with the strict response schema. The model's own thinking stays on (quality over speed);
    if a model rejects the schema, retry once with the prompt alone."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    text = query
    if previous:
        text = _compact_previous(previous) + query
    elif history:
        text = "Earlier in this search session: " + " | ".join(history[-3:]) + "\nNow the shopper says: " + query
    gen = {"responseMimeType": "application/json", "temperature": 0.1}
    if use_schema:
        gen["responseSchema"] = RESPONSE_SCHEMA
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": gen,
    }
    r = requests.post(url, json=body, timeout=60)
    if r.status_code == 400 and use_schema:       # model that rejects the schema: the prompt alone still works
        return call_gemini(api_key, model, query, history, previous, use_schema=False)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(txt)


_OCCASION_WORDS = [  # (regex, occasion, time) - mirrors the vocabulary table in prompt.py
    (r"\b(sangeet|cocktail)\b", "wedding", "evening"), (r"\b(mehendi|mehndi|haldi)\b", "haldi", "day"),
    (r"\b(shaadi|wedding|reception|engagement)\b", "wedding", None), (r"\b(diwali|eid|puja|pooja|festival|navratri|festive)\b", "festive", None),
    (r"\b(office|work|meeting|formal)\b", "office", None), (r"\b(date night|club|night out|party)\b", "party", "evening"),
    (r"\b(gym|running|run|workout|yoga|sports?|training|jogging|cycling)\b", "sports", None), (r"\bbrunch\b", "brunch", "day"), (r"\b(casual|everyday)\b", "casual", None), (r"\bhome\b", "home", None)]
_NEED_PATTERNS = [(r"\boily\b|oil[- ]free", "oily"), (r"\bdry\b", "dry"), (r"\bacne|comedogenic|pimple", "acne"),
                  (r"fragrance[- ]free|no (perfume|fragrance)|unscented", "fragrance-free"), (r"sunscreen|\bspf\b", "sunscreen"),
                  (r"warm light|cosy|cozy", "warm light"), (r"\bsmall\b|compact", "small")]


def _budget(q):
    """(min, max) from 'under 2000', 'above 1500', 'between 1000 and 2000', 'around 4k', '₹6,000'."""
    num = r"(\d[\d,]*(?:\.\d+)?\s?k?)"
    val = lambda x: int(float(x.replace(",", "").replace(" ", "").rstrip("k")) * (1000 if x.strip().endswith("k") else 1))
    if m := re.search(rf"between\s*(?:₹|rs\.?\s?)?{num}\s*(?:and|-|to)\s*(?:₹|rs\.?\s?)?{num}", q):
        return val(m.group(1)), val(m.group(2))
    if m := re.search(rf"(?:around|about|approx\.?|roughly)\s*(?:₹|rs\.?\s?)?{num}", q):
        x = val(m.group(1)); return int(round(x * 0.75, -2)), int(round(x * 1.15, -2))
    lo = re.search(rf"(?:above|over|more than|at least)\s*(?:₹|rs\.?\s?)?{num}", q)
    hi = re.findall(rf"(?:under|below|less than|max|upto|up to|within)\s*(?:₹|rs\.?\s?)?{num}|(?:₹|rs\.?\s?){num}", q)
    hi = [x or y for x, y in hi]
    return (val(lo.group(1)) if lo else None), (val(hi[-1]) if hi else None)


def rule_parse(query, history=None):
    """Offline fallback parser, used only if Gemini is unavailable. Follows the same rules as the prompt, more crudely."""
    # the app annotates follow-ups with "(refers to result #2: name, type, ..., ₹price)"; that describes the item pointed at,
    # it is not a new constraint, so it is removed before parsing ("cheaper" arrives separately as "budget under X")
    strip = lambda x: re.sub(r"\(refers to result[^)]*\)|#\d+", " ", x)
    newq = strip(correct_tokens(query)[0].lower())
    q = (strip(history[-1].lower()) + " " + newq) if history else newq   # a follow-up refines the previous search only
    hard = dict(category=None, gender=None, budget_min=None, budget_max=None, size=None, types=[], style=None)
    soft = dict(occasion=None, time=None, city=None, colour_family=[], colours=[], fabrics=[], fabric_named=False, pairs=None, needs=[])
    maps = []
    hard["budget_min"], hard["budget_max"] = _budget(newq if re.search(r"\d", newq) else q)
    if any(w in q for w in ["lamp", "cushion", "decor", "curtain", "mug", "bedsheet"]): hard["category"] = "lifestyle"
    elif any(w in q for w in ["moisturiser", "moisturizer", "sunscreen", "skin", "cream", "lipstick", "perfume", "makeup"]): hard["category"] = "personal care"
    else: hard["category"] = "fashion"
    if re.search(r"\b(men|mens|man|him|husband|dad|father|brother|boyfriend)\b", q): hard["gender"] = "men"
    elif re.search(r"\b(women|womens|her|she|wife|mom|mother|sister|girlfriend)\b", q) or any(w in q for w in ["lehenga", "saree", "anarkali", "sharara", "dress"]):
        hard["gender"] = "women"
    tq = re.sub(r"\b(no|without|not|free of)\s+\w+", " ", q)   # "no perfume" is a need, not a product type
    for t in ALLOWED["types"]:
        if re.search(rf"(?<![\w-]){re.escape(t)}s?\b", tq): hard["types"].append(t)   # "t-shirt" is not a "shirt"
    if not hard["types"]:  # "anarkali" -> "anarkali set": a first word that identifies exactly one type
        first = collections.Counter(t.split()[0] for t in ALLOWED["types"])
        hard["types"] = [t for t in ALLOWED["types"] if first[t.split()[0]] == 1 and re.search(rf"\b{re.escape(t.split()[0])}s?\b", tq)]
    if "ethnic" in q or any(w in q for w in ["kurta", "lehenga", "saree", "anarkali"]): hard["style"] = "ethnic"
    elif "western" in q or "jeans" in q or "dress" in q: hard["style"] = "western"
    for rx, occ, tm in _OCCASION_WORDS:
        if re.search(rx, q):
            soft["occasion"] = soft["occasion"] or occ
            if tm: soft["time"] = soft["time"] or tm
            word = re.search(rx, q).group(0)
            if word != occ:
                maps.append(dict(phrase=word, maps_to=f"occasion {occ}" + (f", {tm}" if tm else "")))
    if "daytime" in q or "day " in q or "morning" in q: soft["time"] = "day"
    if "evening" in q or "night" in q: soft["time"] = "evening"
    for c in WEATHER:
        if c in q: soft["city"] = c
    for cf in ALLOWED["colour_family"]:
        if cf in q: soft["colour_family"].append(cf)
    # named colours (from the new message only; "silver jewellery" is a pairing, not a colour)
    cq = re.sub(r"\b(silver|gold|golden|oxidi[sz]ed)\s+(jewell?ery|jewelry|tone[ds]?)\b", " ", newq)
    for phrase in sorted(set(COLOUR_PHRASES) | set(COLOUR_WORDS) | set(COLOUR_SYNONYMS), key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", cq) and not any(phrase in c for c in soft["colours"]):
            soft["colours"].append(phrase)
    if soft["colours"]: soft["colour_family"] = []
    for f in ALLOWED["fabrics"]:
        if re.search(rf"\b{re.escape(f)}\b", q): soft["fabrics"].append(f)
    soft["fabric_named"] = bool(soft["fabrics"])
    if "breathable" in q or "humid" in q or "summer" in q:
        soft["fabrics"] = sorted(set(soft["fabrics"]) | {"cotton", "linen", "chanderi", "mul cotton"})
        maps.append(dict(phrase="breathable / humid", maps_to="cotton, linen, chanderi, mul cotton"))
    if re.search(r"\bwinter|cold\b", q):
        soft["fabrics"] = sorted(set(soft["fabrics"]) | {"wool", "fleece", "velvet"})
        maps.append(dict(phrase="winter", maps_to="wool, fleece, velvet"))
    if "silver" in q: soft["pairs"] = "silver"; maps.append(dict(phrase="pairs with silver", maps_to="silver-friendly colours & trims"))
    if "gold" in q: soft["pairs"] = "gold"
    if hard["category"] != "fashion":
        for rx, n in _NEED_PATTERNS:
            if re.search(rx, q) and n not in soft["needs"]: soft["needs"].append(n)
    m2 = SIZE_RE.search(query)
    if m2: hard["size"] = m2.group(1).upper()
    stage = 3 if maps else 1
    clarify = None
    if hard["category"] == "fashion" and soft["occasion"] in ("wedding", "party") and not hard["style"] and not hard["types"]:
        stage, clarify = 4, dict(question=f"Ethnic or western for the {soft['occasion']}?", options=["Ethnic", "Western", "Show both"])
    return dict(query_type="product_search", reply=None, stage=stage, interpretation="Parsed with offline rules (Gemini unavailable)",
                hard=hard, soft=soft, mappings=maps, clarify=clarify)


# Values a model may return instead of the catalog's word (used by the validator, mainly when the schema is not enforced)
VALUE_ALIASES = {"male": "men", "man": "men", "gents": "men", "mens": "men", "female": "women", "woman": "women", "ladies": "women",
                 "womens": "women", "gym": "sports", "running": "sports", "workout": "sports", "fitness": "sports", "yoga": "sports",
                 "training": "sports", "athleisure": "sports", "activewear": "sports", "dri-fit": "quick-dry", "dri fit": "quick-dry",
                 "dry-fit": "quick-dry", "quick dry": "quick-dry", "rapid-dry": "quick-dry", "moisture-wicking": "quick-dry",
                 "shaadi": "wedding", "sangeet": "wedding", "reception": "wedding", "mehendi": "haldi", "mehndi": "haldi",
                 "diwali": "festive", "festival": "festive", "work": "office", "formal": "office", "night": "evening",
                 "daytime": "day", "morning": "day", "afternoon": "day", "home decor": "home decor"}


def _closest(value, allowed, cutoff=0.82):
    """Map a near-miss to an allowed value: exact, alias ('kurti' -> 'kurta', 'male' -> 'men'), head word, or close spelling."""
    v = str(value).strip().lower()
    if v in allowed: return v
    if VALUE_ALIASES.get(v) in allowed: return VALUE_ALIASES[v]
    v2 = ALIASES.get(v, v)
    if v2 in allowed: return v2
    if v2.endswith("s") and v2[:-1] in allowed: return v2[:-1]
    m = difflib.get_close_matches(v2, list(allowed), n=1, cutoff=cutoff)
    return m[0] if m else None


_NEED_HINTS = {"oil": "oily", "matte": "oily", "mattif": "oily", "dry": "dry", "nourish": "dry", "acne": "acne", "comedogenic": "acne",
               "pimple": "acne", "breakout": "acne", "fragrance": "fragrance-free", "perfume": "fragrance-free", "unscented": "fragrance-free",
               "sensitive": "fragrance-free", "sunscreen": "sunscreen", "spf": "sunscreen", "makeup": "sunscreen", "warm": "warm light",
               "cosy": "warm light", "cozy": "warm light", "yellow light": "warm light", "small": "small", "compact": "small", "tiny": "small"}


def _valid_colour(v):
    v = re.sub(r"(ish|-coloured|-colored| colou?r)$", "", str(v).lower().strip())
    if v in COLOUR_SYNONYMS: return v
    return _closest(v, set(COLOUR_PHRASES) | set(COLOUR_WORDS), cutoff=0.8)


QUERY_TYPES = ("product_search", "out_of_catalog", "support", "other")


def validate_intent(intent):
    """Repair or drop anything the search can't use, so a model slip can't silently break results. Returns (intent, notes)."""
    notes = []
    it = dict(intent or {})
    h = dict(it.get("hard") or {}); s = dict(it.get("soft") or {})
    qt = str(it.get("query_type") or "product_search").lower().replace(" ", "_")
    if qt not in QUERY_TYPES:
        notes.append(f"query_type: “{it.get('query_type')}” → product_search"); qt = "product_search"
    it["query_type"] = qt
    it["reply"] = (str(it.get("reply")).strip() or None) if it.get("reply") and qt != "product_search" else None
    if qt in ("support", "other"):   # not a search: no constraints, stage 6
        it.update(stage=6, clarify=None, mappings=[], hard={k: None for k in h} | {"types": []},
                  soft={k: ([] if isinstance(v, list) else None) for k, v in s.items()})
        it["soft"]["fabric_named"] = False
        it["interpretation"] = str(it.get("interpretation") or "").strip()
        return it, notes

    def one(sec, key, allowed):
        v = sec.get(key)
        if v in (None, ""): sec[key] = None; return
        c = _closest(v, allowed)
        if c != v: notes.append(f"{key}: “{v}” → {c or 'dropped'}")
        sec[key] = c

    def many(sec, key, allowed, mapper=None):
        out = []
        for v in sec.get(key) or []:
            c = mapper(v) if mapper else _closest(v, allowed)
            if c != v: notes.append(f"{key}: “{v}” → {c or 'dropped'}")
            if c and c not in out: out.append(c)
        sec[key] = out

    one(h, "category", ALLOWED["category"]); one(h, "gender", ALLOWED["gender"]); one(h, "style", ALLOWED["style"])
    many(h, "types", ALLOWED["types"])
    for k in ("budget_min", "budget_max"):
        v = h.get(k)
        try:
            h[k] = int(float(str(v).replace(",", "").replace("₹", ""))) if v not in (None, "", 0) else None
        except ValueError:
            notes.append(f"{k}: “{v}” → dropped"); h[k] = None
    if h.get("budget_min") and h.get("budget_max") and h["budget_min"] > h["budget_max"]:
        notes.append("budget_min above budget_max → dropped budget_min"); h["budget_min"] = None
    if h.get("size") not in (None, ""):
        sz = str(h["size"]).upper().strip()
        if sz not in SIZE_ORDER and sz not in WAIST_ORDER:
            notes.append(f"size: “{h['size']}” → dropped"); sz = None
        h["size"] = sz
    else:
        h["size"] = None

    one(s, "occasion", ALLOWED["occasion"]); one(s, "time", ALLOWED["time"])
    if s.get("pairs") not in ("silver", "gold"): s["pairs"] = None
    many(s, "colour_family", ALLOWED["colour_family"])
    many(s, "fabrics", ALLOWED["fabrics"])
    many(s, "colours", COLOUR_WORDS, mapper=_valid_colour)
    many(s, "needs", ALLOWED["needs"], mapper=lambda v: _closest(v, ALLOWED["needs"]) or next(
        (n for k, n in _NEED_HINTS.items() if k in str(v).lower()), None))
    if s["needs"] and h.get("category") == "fashion":   # skin / home needs can't be checked on clothes; they'd filter out everything
        notes.append(f"needs {s['needs']} → dropped (not checkable on fashion)"); s["needs"] = []
    s["fabric_named"] = bool(s.get("fabric_named"))
    s["city"] = (s.get("city") or None) and str(s["city"]).lower()
    it["hard"], it["soft"] = h, s

    try:
        stage = int(it.get("stage") or 1)
    except (TypeError, ValueError):
        stage = 1
    cl = it.get("clarify")
    if stage == 4 and not (cl and cl.get("question") and len(cl.get("options") or []) >= 2):
        notes.append("stage 4 without a usable question → stage 3"); stage, it["clarify"] = 3, None
    if stage != 4 and cl:
        it["clarify"] = None
    if cl and stage == 4:
        it["clarify"] = dict(question=str(cl["question"]), options=[str(o) for o in cl["options"]][:4])
    it["stage"] = stage if stage in (1, 3, 4, 5) else (3 if stage == 6 else 1)   # 6 is only for support / other
    it["interpretation"] = str(it.get("interpretation") or "").strip()
    it["mappings"] = [m for m in (it.get("mappings") or []) if isinstance(m, dict) and m.get("phrase")]
    return it, notes


def understand(query, api_key, models, history=None, previous=None):
    """Run the intent agent with model fallback, then validate; returns (intent, model_used, log)."""
    log = []
    out, used = None, "offline rules"
    if api_key:
        for model in models:
            t0 = time.time()
            try:
                out = call_gemini(api_key, model, query, history, previous)
                log.append(f"{model}: ok in {time.time()-t0:.1f}s")
                used = model
                break
            except Exception as e:
                log.append(f"{model}: {str(e)[:90]}")
    else:
        log.append("No GEMINI_API_KEY set")
    if out is None and api_key:   # every model failed: the caller falls back to normal search (safety net)
        return None, "failed", log
    if out is None:               # no key at all (local development): crude offline rules
        out = rule_parse(query, history)
    out, notes = validate_intent(out)
    log.append("validator: " + ("; ".join(notes) if notes else "all values valid"))
    return out, used, log


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
        if occ.get("fabrics") and not soft.get("fabric_named"):   # e.g. gym -> quick-dry synthetics, unless a fabric was named
            soft["fabrics"] = sorted(set(soft.get("fabrics") or []) | set(occ["fabrics"]))
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
    if h.get("budget_min") and p["price"] < h["budget_min"] and "budget" not in drop: return False, ["budget"]
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
            "warm light": "warm" in blob, "small": "small" in blob or "compact" in blob,
            "dry": "dry skin" in blob or "nourish" in blob or "shea" in blob}.get(n, True)


def _fabric_ok(p, s):
    """True / False, or None when the listing states no fabric and the fabric was only inferred (e.g. from 'breathable')."""
    if p["fabric"] in s["fabrics"]: return True
    if not p["fabric"] and not s.get("fabric_named"): return None
    return False


def _colour_ok(p, colours):
    c = p["colour"]
    return any(t in c for col in colours for t in colour_targets(col))


def check_soft(p, s):
    """Verifier: per-constraint result for a product: True (pass), False (fail) or None (unknown: not stated in the listing)."""
    checks = []
    if s.get("fabrics"):
        checks.append(("fabric", _fabric_ok(p, s), p["fabric"] or "not stated"))
    if s.get("colours"):
        checks.append(("colour " + "/".join(s["colours"]), _colour_ok(p, s["colours"]), p["colour"]))
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
    if h.get("budget_min") and "budget" not in drop: m &= _PRICE >= h["budget_min"]
    if h.get("types") and "types" not in drop:
        m &= _isin(_TYP, _TYP_M, [t for t in _TYP_M if _type_match(h["types"], t)])
    if h.get("style") in ("ethnic", "western"): m &= _STY == _STY_M.get(h["style"], -1)
    if h.get("size") and "size" not in drop: m &= _FREE | _SIZE_M.get(str(h["size"]).upper(), _ZERO)
    return m


_COLOUR_STR = [p["colour"] for p in _PL]
_COLOUR_M = {}


def _soft_masks(s):
    """One boolean array per active soft constraint: True where the check does not fail (same semantics as check_soft)."""
    out = []
    if s.get("fabrics"):
        m = _isin(_FAB, _FAB_M, s["fabrics"])
        if not s.get("fabric_named"): m = m | (_FAB == _FAB_M.get("", -1))   # unknown fabric allowed when inferred
        out.append(m)
    if s.get("colours"):
        key = tuple(sorted(s["colours"]))
        if key not in _COLOUR_M:
            targets = [t for c in key for t in colour_targets(c)]
            _COLOUR_M[key] = np.array([any(t in c for t in targets) for c in _COLOUR_STR])
        out.append(_COLOUR_M[key])
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


# weakest first (solution doc: colour shade, fabric, pairing, style words); occasion type is near-hard, so it goes last
RELAX_ORDER = ["colours", "colour_family", "fabrics", "pairs", "time", "occasion"]


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
    # listings that only pass because their fabric is unknown rank below ones that state a matching fabric
    unknown = (_FAB == _FAB_M.get("", -1)) * 0.3 if s.get("fabrics") and not s.get("fabric_named") else 0
    score = _RATING + prefer * 0.5 + _JITTER - unknown
    chosen = _top(np.flatnonzero(ok), score, max_results, per_brand=2)
    near = []
    if not len(chosen):  # show near misses on hard constraints, e.g. over budget: the cheapest few
        idx = np.flatnonzero(_hard_mask(h, drop=("budget",)))
        near = [_PL[i] for i in idx[np.argsort(_PRICE[idx], kind="stable")][:3]]
    return [(_PL[i], check_soft(_PL[i], s)) for i in chosen], relaxed, trace, near


# ------------------------------------------------------------------ browse (home page)
DEPARTMENTS = {"All": None, "Women": ("gender", "women"), "Men": ("gender", "men"), "Ethnic": ("style", "ethnic"),
               "Western": ("style", "western"), "Home": ("category", "lifestyle"), "Beauty": ("category", "personal care")}


def _featured_order():
    """Catalog interleaved across types so the first page is not all shirts, with the demo products mixed in."""
    by_type = collections.defaultdict(list)
    for i in np.argsort(-(_RATING + _JITTER), kind="stable"):
        by_type[_PL[i]["type"]].append(int(i))
    demo = [i for i, p in enumerate(_PL) if p.get("source") == "demo"]
    queues = sorted((q for q in by_type.values()), key=len, reverse=True)
    rest, k = [], 0
    while any(queues):
        for q in queues:
            if k < len(q) and q[k] not in demo:
                rest.append(q[k])
        k += 1
        if k > max(len(q) for q in queues): break
    # real listings (with photos) lead; the illustrative demo products are mixed in from the second row on
    out = rest[:8]
    for k, i in enumerate(demo):
        out += [i] + rest[8 + 4 * k: 12 + 4 * k]
    return out + rest[8 + 4 * len(demo):]


_FEATURED = np.array(_featured_order(), dtype=np.int64)


def _dept_mask(dept):
    m = np.ones(_N, bool)
    spec = DEPARTMENTS.get(dept)
    if spec:
        field, val = spec
        codes, mapping = {"gender": (_GEN, _GEN_M), "style": (_STY, _STY_M), "category": (_CAT, _CAT_M)}[field]
        m &= codes == mapping.get(val, -1)
        if field == "gender": m &= _CAT == _CAT_M.get("fashion", -1)
    return m


def browse_types(dept):
    """Product types in a department, most common first."""
    c = collections.Counter(_PL[i]["type"] for i in np.flatnonzero(_dept_mask(dept)))
    return [t for t, _ in c.most_common()]


def browse(dept="All", ptype=None, sort="Featured"):
    """Ids for the home page grid."""
    m = _dept_mask(dept)
    if ptype: m &= _TYP == _TYP_M.get(ptype, -1)
    if sort == "Featured":
        idx = _FEATURED[m[_FEATURED]]
    else:
        idx = np.flatnonzero(m)
        idx = idx[np.argsort(_PRICE[idx] if sort.startswith("Price: low") else -_PRICE[idx], kind="stable")]
    return [_PL[i]["id"] for i in idx]


def _kw_stem(t):
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def _kw_tokens(text):
    """Keyword tokens; 't-shirt' stays one word so a t-shirt search doesn't match every shirt."""
    text = re.sub(r"\bt-?shirts?\b|\btees?\b", " tshirt ", text.lower())
    return {_kw_stem(t) for t in re.findall(r"[a-z]+", text) if len(t) > 1}


_KW_INDEX = collections.defaultdict(list)
for _i, _p in enumerate(_PL):
    for _t in _kw_tokens(f"{_p['name']} {_p['type']} {_p['colour']} {_p['fabric']} {_p['gender']}"):
        _KW_INDEX[_t].append(_i)
_KW_INDEX = {t: np.array(v, dtype=np.int64) for t, v in _KW_INDEX.items()}


def query_gender(query):
    """Gender stated in a short query, if any ("men", "women's" ...)."""
    q = query.lower()
    if re.search(r"\b(women|womens|women's|ladies|girls?|her)\b", q): return "women"
    if re.search(r"\b(men|mens|men's|gents|boys?|him)\b", q): return "men"
    return None


def keyword_filters(query, gender=None):
    """What a short query asks for, as filters the shopper can see and remove: gender, item types, colours, size,
    and any other catalog words (fabric, fit...). Each filter keeps the query words it came from."""
    toks = _kw_tokens(query) - _KW_STOP
    out = dict(gender=None, gender_from=None, types=[], colours=[], size=None, words=[])
    g = query_gender(query)
    out["gender"], out["gender_from"] = (g, "query") if g else ((gender, "profile") if gender in ("women", "men") else (None, None))
    used = set()
    for t in sorted(ALLOWED["types"], key=len, reverse=True):          # "kurta set" before "kurta"
        tt = _kw_tokens(t)
        if tt and tt <= toks and not tt <= used:
            out["types"].append((t, sorted(tt))); used |= tt
    for t in sorted(toks - used):
        if t in COLOUR_SYNONYMS or t in COLOUR_WORDS:
            out["colours"].append((t, [t])); used.add(t)
    size = SIZE_RE.search(query)
    if size: out["size"] = size.group(1).upper()
    gender_words = {"men", "man", "women", "woman", "ladies", "gent", "boy", "girl", "her", "him"}
    out["words"] = [t for t in sorted(toks - used - gender_words) if t in _KW_INDEX]
    return out


_KW_STOP = {"for", "the", "and", "with", "in", "of", "an", "to", "my", "me", "some", "size", "buy", "show", "want", "need", "new", "best"}


def keyword_search(query, max_results=8, gender=None, info=None):
    """Normal search. Every meaningful word must match ("green tshirt" = green AND t-shirt; a colour also accepts close
    shades), falling back to partial matches only if nothing matches all of them. gender (from the shopper's profile)
    keeps fashion results to that gender + unisex, unless the query names a gender itself."""
    toks = _kw_tokens(query) - _KW_STOP
    size = SIZE_RE.search(query)
    hits = np.zeros(_N)
    every = np.ones(_N, bool)
    used = []
    for t in toks:
        posts = [_KW_INDEX[v] for v in {_kw_stem(w) for w in COLOUR_SYNONYMS.get(t, [t])} if v in _KW_INDEX]
        if not posts:
            continue   # a word the catalog doesn't know can't narrow anything
        m = np.zeros(_N, bool)
        for ps in posts: m[ps] = True
        hits += m; every &= m; used.append(t)
    g = query_gender(query) or gender
    base = np.ones(_N, bool)
    if g in ("women", "men"):
        base &= (_CAT != _CAT_M.get("fashion", -1)) | (_GEN == _GEN_M.get(g, -1)) | (_GEN == _GEN_M.get("unisex", -1))
    if size: base &= _FREE | _SIZE_M.get(size.group(1).upper(), _ZERO)
    ok = every & base if used else np.zeros(_N, bool)
    mode = "all words"
    if not ok.any() and used:
        ok, mode = (hits > 0) & base, "partial (nothing matched every word)"
    if info is not None:
        info.update(words=used, mode=mode, gender=g)
    return [_PL[i] for i in _top(np.flatnonzero(ok), hits + _RATING + _JITTER, max_results, per_brand=3)]


def why_this(p, intent):
    s = intent.get("soft", {})
    bits = []
    if p["fabric"] in BREATHABLE and (s.get("fabrics") or s.get("city")):
        bits.append(f"breathable {p['fabric']}")
    if s.get("colours") and _colour_ok(p, s["colours"]):
        bits.append(f"in {p['colour']}")
    if s.get("colour_family") and p["colour_family"] in s["colour_family"]:
        bits.append(f"{p['colour']} suits {s.get('time') or 'the'} {s.get('occasion') or 'look'}".replace("the look", "the look"))
    if s.get("pairs") == "silver" and p["pairs"] in ("silver", "any"):
        bits.append("works with silver")
    h = intent.get("hard", {})
    if h.get("budget_max") and not h.get("budget_min"):
        bits.append(f"₹{h['budget_max'] - p['price']:,} under budget" if p["price"] <= h["budget_max"] else "over budget")
    elif h.get("budget_min") or h.get("budget_max"):
        bits.append("within your budget")
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
