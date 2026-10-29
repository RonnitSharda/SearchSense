"""SearchSense agent: router, Gemini intent agent, tools, verifier, fit layer."""
import json, re, time, difflib, zlib, collections, threading, datetime
import numpy as np
import requests
from catalog import (PRODUCTS, P as DEMO_PRODUCTS, BREATHABLE, HEAVY, SIZE_ORDER, WAIST_ORDER, ANCHOR_BRANDS,
                     OCCASION_RULES, MONTHS, WARM, WARM_LAYERS)
import base64
from attributes import FITS, PATTERNS, SLEEVES, NECKS, PRINTS
from prompt import NEEDS, build_system_prompt, build_response_schema, build_label_prompt

# ------------------------------------------------------------------ vocabulary
_FIELDS = ("name", "type", "colour", "fabric", "brand", "style", "colour_family", "gender")
_TOKEN_FREQ = collections.Counter()
for p in PRODUCTS.values():
    _TOKEN_FREQ.update({w for f in _FIELDS for w in re.findall(r"[a-z]+", str(p[f]).lower())})
# the demo products' words (anarkali, chanderi...) stay in the vocabulary even though the products aren't shown
_DEMO_TOKENS = {w for p in DEMO_PRODUCTS for f in _FIELDS for w in re.findall(r"[a-z]+", str(p[f]).lower())}
# words from the data must appear on >= 3 products (or be demo words), so one-off brand fragments aren't "correct" spellings
# place names are vocabulary only (so the spell-checker leaves them alone); their weather comes from the AI
_PLACES = set("""mumbai delhi pune jaipur chennai kolkata bengaluru bangalore hyderabad goa manali shimla leh ladakh srinagar
 kashmir darjeeling gangtok ooty munnar mussoorie nainital udaipur rishikesh coorg kodaikanal""".split())
_STATIC_VOCAB = _DEMO_TOKENS | set("""for a an the in and or with under below above size sizes men women mens womens
 kurta kurti shirt jeans lehenga saree dress set lamp moisturiser sunscreen jacket white black blue
 green pink yellow red beige ivory pastel cotton linen silk wedding haldi office casual party festive
 that pairs pair jewellery silver gold breathable humid daytime day evening mumbai delhi pune
 under rs inr high waist straight wear outfit ethnic western oily acne prone skin fragrance free sits
 well sunscreen minimal reading corner small warm light lamp table jewelry jewellery something look
 humid breathable daytime pastel sangeet haldi brunch moisturizer moisturiser chanderi
 gym running run workout yoga sports sport training jogging trek trekking hiking travel beach swimming cycling
 i im my me want need needs looking show find buy clothes clothing trip trips vacation holiday holidays tour visit visiting
 winter summer cold hot rainy monsoon chilly cool weather layers""".split()) | set(MONTHS) | _PLACES   # hand-written words win spelling ties
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


def _osa(a, b, maxd):
    """Edit distance with adjacent swaps (Damerau / optimal string alignment), stopping early past maxd."""
    if abs(len(a) - len(b)) > maxd:
        return maxd + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > maxd:
            return maxd + 1
        prev2, prev = prev, cur
    return prev[-1]


# correction targets: catalog words, not function words ("wite" means white, not "with") or fragments like "gm"
_NOT_TARGETS = {"with", "that", "for", "the", "and", "under", "below", "above", "well", "sits", "free", "look", "pair", "pairs",
                "wear", "high", "something", "corner", "small", "prone", "skin", "rs", "inr", "day"}
_VOCAB_LIST = sorted(w for w in VOCAB if len(w) >= 4 and w not in _NOT_TARGETS)   # typos are corrected to real words of 4+ letters


def spelling_candidates(t, maxd=None):
    """Catalog words within 1 edit (2 for long words), best first: fewest edits, then hand-written words, then commoner words.
    Any letter can be wrong, including the first ("vlue" -> blue)."""
    maxd = maxd or (1 if len(t) <= 5 else 2)
    c = [(d, w) for w in _VOCAB_LIST if abs(len(w) - len(t)) <= maxd and (d := _osa(t, w, maxd)) <= maxd]
    return sorted(c, key=lambda x: (x[0], -(x[1] in _STATIC_VOCAB), -_TOKEN_FREQ[x[1]]))


def correct_tokens(q, ambiguous=None):
    """Light spelling correction against catalog vocabulary (stage 2). If two corrections are equally likely, the word is
    left alone and both are offered in `ambiguous` ({word: [options]}) so the app can ask "Did you mean ...?"."""
    out, fixes = [], []
    for tok in q.split():
        t = tok.lower()
        if t in ALIASES and ALIASES[t] != t:
            out.append(ALIASES[t]); fixes.append((tok, ALIASES[t])); continue
        if len(t) <= 3 or t in VOCAB or not t.isalpha():   # 3-letter words ("gym") are too short to correct safely
            out.append(tok); continue
        c = spelling_candidates(t)
        if not c:
            far = spelling_candidates(t, (1 if len(t) <= 5 else 2) + 1) if len(t) >= 5 else []
            if far and ambiguous is not None:   # too far to fix silently ("lenin"): ask "Did you mean linen?"
                ambiguous[tok] = [w for _, w in far[:3]]
            out.append(tok); continue
        best = c[0]
        rivals = [w for d, w in c[1:] if d == best[0] and (w in _STATIC_VOCAB) == (best[1] in _STATIC_VOCAB)
                  and _TOKEN_FREQ[w] * 3 > _TOKEN_FREQ[best[1]]]
        if rivals and ambiguous is not None:   # e.g. two common words one letter away: ask instead of guessing
            ambiguous[tok] = [best[1]] + rivals[:2]
            out.append(tok); continue
        out.append(best[1]); fixes.append((tok, best[1]))
    return " ".join(out), fixes


def route(query, ai=False):
    """Light classifier: decides stage 0 / 2 / 6 locally, or hands complex queries to the agent.
    With AI available (ai=True), any word the catalog doesn't know goes to the agent, which fixes spelling or asks;
    the local spell-checker is only the fallback when there is no model."""
    q = query.strip()
    ql = q.lower()
    if OUT_OF_SCOPE.search(ql):
        return dict(stage=6, label="Out of scope", reason="Order or returns question, not a product search")
    amb = {}
    corrected, fixes = correct_tokens(q, amb)
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
    if ai and (fixes or amb):
        typed = ", ".join([a for a, _ in fixes] + list(amb))
        return dict(stage="agent", label="Spelling: sent to agent", query=q, fixes=[],
                    reason=f"Unrecognised word(s) {typed}: the agent fixes the spelling or asks")
    if amb:   # not sure which word was meant: search what we can and ask "Did you mean ...?"
        return dict(stage=2 if fixes else 0, label="Spelling unclear", query=corrected, fixes=fixes, did_you_mean=amb,
                    reason="A word could be more than one catalog word, so the shopper is asked")
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
    fit=FITS, pattern=PATTERNS, sleeve=SLEEVES, neck=NECKS,
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


SYSTEM = build_system_prompt(ALLOWED, TYPES_BY_CATEGORY, sorted(set(COLOUR_WORDS) | set(COLOUR_SYNONYMS)),
                            this_month=datetime.date.today().strftime("%B"))
RESPONSE_SCHEMA = build_response_schema(ALLOWED)


_HARD_KEEP = ("category", "gender", "budget_min", "budget_max", "size", "types", "style")
_SOFT_KEEP = ("occasion", "time", "city", "month", "weather", "colour_family", "colours", "fabrics", "fit", "pattern", "sleeve", "neck",
              "pairs", "needs")
# style attributes read from each listing (attributes.py): a stated different value fails, an unstated one is allowed
# (ranked lower); a request for "printed" accepts any print
STYLE_ATTRS = ("fit", "pattern", "sleeve", "neck")


def _style_ok_values(attr, want):
    return sorted(PRINTS) if attr == "pattern" and want == "printed" else [want]


def _style_label(attr, want):
    return {"fit": f"{want} fit", "pattern": "print" if want == "printed" else f"{want}"}.get(attr, want)


def merge_followup(intent, prev):
    """A refinement keeps the previous search: anything the new message leaves empty is carried over ("outfits for trekking"
    then "pink" = pink trekking outfits, not every pink product). A pivot (a different product, occasion or category) is a
    new search that keeps only who it's for, the size and the budget. Returns (intent, [what was kept])."""
    if not prev:
        return intent, []
    h, s = intent.setdefault("hard", {}), intent.setdefault("soft", {})
    ph, ps = prev.get("hard") or {}, prev.get("soft") or {}
    empty = lambda v: v in (None, [], "")
    pivot = (not empty(h.get("types")) and not empty(ph.get("types")) and set(h["types"]) != set(ph["types"])) \
        or (not empty(h.get("types")) and empty(ph.get("types")) and not empty(ps.get("occasion")) and not empty(s.get("occasion"))
            and s["occasion"] != ps["occasion"]) \
        or (not empty(s.get("occasion")) and not empty(ps.get("occasion")) and s["occasion"] != ps["occasion"]) \
        or (not empty(h.get("category")) and not empty(ph.get("category")) and h["category"] != ph["category"])
    kept = []
    for k in (("gender", "size", "budget_min", "budget_max") if pivot else _HARD_KEEP):
        if empty(h.get(k)) and not empty(ph.get(k)):
            h[k] = ph[k]; kept.append(k.replace("_", " "))
    if not pivot:
        for k in _SOFT_KEEP:
            if k in ("colour_family", "colours") and (s.get("colours") or s.get("colour_family")):
                continue   # a new colour replaces the old colour, whichever way it was said
            if k == "weather" and s.get("city") and s.get("city") != ps.get("city"):
                continue
            if empty(s.get(k)) and not empty(ps.get(k)):
                s[k] = ps[k]; kept.append(k.replace("_", " "))
                if k == "fabrics": s["fabric_named"] = bool(ps.get("fabric_named"))
    return intent, kept


def _compact_previous(prev):
    """Previous search's constraints, without empty fields, for follow-ups."""
    if not prev: return ""
    out = {}
    for sec in ("hard", "soft"):
        d = {k: v for k, v in (prev.get(sec) or {}).items() if v not in (None, [], "", False) and k not in ("prefer_colour_family", "prefer_types", "climate", "weather", "layer_tip")}
        if d: out[sec] = d
    return f"[Previous search constraints: {json.dumps(out, ensure_ascii=False)}] " if out else ""


# Every Gemini call, newest last, for the admin tab: model, HTTP result, seconds and token counts (thinking included).
# Kept in memory for this server process, shared by all visitors; it resets when the app restarts.
CALL_LOG = collections.deque(maxlen=500)
_CTX = threading.local()   # each visitor's script runs in its own thread, so the tag links calls to that visitor's search


def set_log_tag(tag):
    """Calls made from now on (in this thread) are tagged with this search id; None for calls outside a search."""
    _CTX.tag = tag


def _request_text(body):
    """What we sent, as readable text (photos replaced by a placeholder)."""
    out = []
    for c in body.get("contents") or []:
        for part in c.get("parts") or []:
            if "text" in part: out.append(part["text"])
            elif "inline_data" in part:
                out.append(f"[photo: {part['inline_data'].get('mime_type')}, {len(part['inline_data'].get('data', '')) * 3 // 4 // 1024} KB]")
    return "\n".join(out)


def _log_call(purpose, model, t0, r=None, err=None, body=None):
    d = dict(at=time.time(), purpose=purpose, model=model, secs=round(time.time() - t0, 2), tag=getattr(_CTX, "tag", None),
             request=_request_text(body or {}), system_prompt=bool((body or {}).get("systemInstruction")),
             schema=bool(((body or {}).get("generationConfig") or {}).get("responseSchema")))
    if r is None:
        d.update(status="no response", note=str(err)[:200], reply=str(err))
    else:
        try:
            j = r.json()
        except Exception:
            j = {}
        u = j.get("usageMetadata") or {}
        d.update(status=r.status_code, prompt_tokens=u.get("promptTokenCount"), cached_tokens=u.get("cachedContentTokenCount"),
                 thinking_tokens=u.get("thoughtsTokenCount"), output_tokens=u.get("candidatesTokenCount"))
        if r.status_code != 200:
            d["note"] = str((j.get("error") or {}).get("message") or r.text)[:200]
        try:
            d["reply"] = j["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            d["reply"] = r.text[:20000]   # error body, or an answer without text
    CALL_LOG.append(d)


# Reliability: free-tier requests can queue for minutes (we saw 350s). Each call gets a time limit; a model that times
# out or is refused (quota, overload) is tried last for a while, and the last model that answered is tried first.
TIMEOUT = None                         # no time limit for now (quality over speed); set e.g. (5, 20) to cap waits
COOLDOWN = {429: 60, "timeout": 300}   # quota refusals often clear within a minute; a queueing model stays at the back longer
_LAST_OK, _DOWN_UNTIL = [None], {}


def model_order(models):
    """Last model that answered first; models that failed recently go last (never dropped: a slow answer beats none)."""
    now = time.time()
    return sorted(models, key=lambda m: (_DOWN_UNTIL.get(m, 0) > now, m != _LAST_OK[0]))


def _post_logged(purpose, model, url, body):
    t0 = time.time()
    try:
        r = requests.post(url, json=body, timeout=TIMEOUT)
    except Exception as e:
        timed_out = isinstance(e, requests.Timeout)
        _DOWN_UNTIL[model] = time.time() + COOLDOWN["timeout"]
        err = RuntimeError("no answer in time, trying the next model") if timed_out else e
        _log_call(purpose, model, t0, err=err, body=body)
        raise err
    _log_call(purpose, model, t0, r, body=body)
    if r.status_code == 200:
        _LAST_OK[0] = model; _DOWN_UNTIL.pop(model, None)
    elif r.status_code == 429 or r.status_code >= 500:
        _DOWN_UNTIL[model] = time.time() + COOLDOWN.get(r.status_code, COOLDOWN["timeout"])
    return r


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
    r = _post_logged("search intent" if use_schema else "search intent (retry without schema)", model, url, body)
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
    (r"\b(gym|running|run|workout|yoga|sports?|training|jogging|cycling)\b", "sports", None), (r"\bbrunch\b", "brunch", "day"), (r"\b(casual|everyday)\b", "casual", None),
    (r"\b(trips?|travel|vacation|holidays?|tour)\b", "casual", None), (r"\bhome\b", "home", None)]
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
    soft = dict(occasion=None, time=None, city=None, month=None, fit=None, colour_family=[], colours=[], fabrics=[], fabric_named=False,
                pairs=None, needs=[])
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
    soft["fit"] = next((f for f, rx in (("relaxed", r"\b(loose|relaxed|baggy|oversized|wide[- ]leg|comfy fit)\b"),
                                         ("slim", r"\b(slim|skinny|fitted|tight)\b"), ("regular", r"\b(regular fit|straight)\b"))
                        if re.search(rx, newq)), None)
    for attr, rules in (("pattern", (("floral", r"\bflor(al|a)\b|\bflower"), ("striped", r"\bstripe"), ("checked", r"\bcheck"),
                                     ("polka dots", r"\bpolka"), ("embroidered", r"\bembroider"), ("printed", r"\bprint"),
                                     ("solid", r"\b(solid|plain)\b"))),
                        ("sleeve", (("sleeveless", r"sleeveless|strappy"), ("3/4 sleeves", r"3/4|three[- ]quarter"),
                                    ("long sleeves", r"full[- ]sleeve|long[- ]sleeve"), ("short sleeves", r"half[- ]sleeve|short[- ]sleeve"))),
                        ("neck", (("v-neck", r"\bv[- ]neck"), ("round neck", r"round neck"), ("off-shoulder", r"off[- ]shoulder"),
                                  ("mandarin collar", r"mandarin"), ("collar", r"\bcollar")))):
        soft[attr] = next((v for v, rx in rules if re.search(rx, newq)), None)
    soft["city"] = next((c for c in sorted(_PLACES) if re.search(rf"\b{c}\b", q)), None)   # no weather offline: that needs the AI
    soft["month"] = next((m for m in MONTHS if re.search(rf"\b{m[:3]}(?:{m[3:]})?\b", q)), None)
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
                 "daytime": "day", "morning": "day", "afternoon": "day", "home decor": "home decor",
                 "loose": "relaxed", "baggy": "relaxed", "oversized": "relaxed", "wide": "relaxed", "wide leg": "relaxed",
                 "comfort": "relaxed", "skinny": "slim", "fitted": "slim", "tight": "slim", "straight": "regular", "classic": "regular",
                 "flowery": "floral", "flower": "floral", "flowers": "floral", "print": "printed", "prints": "printed", "stripes": "striped",
                 "stripe": "striped", "checks": "checked", "check": "checked", "plaid": "checked", "plain": "solid", "polka": "polka dots",
                 "embroidery": "embroidered", "half sleeves": "short sleeves", "short sleeve": "short sleeves",
                 "full sleeves": "long sleeves", "long sleeve": "long sleeves", "three-quarter sleeves": "3/4 sleeves",
                 "strapless": "sleeveless", "v neck": "v-neck", "crew neck": "round neck", "mandarin": "mandarin collar",
                 "off shoulder": "off-shoulder", "turtle neck": "high neck", "halter": "halter neck"}


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
    conf = str(it.get("confidence") or "high").lower()
    it["confidence"] = conf if conf in ("high", "medium", "low") else "high"
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
    for attr in STYLE_ATTRS:   # fit, print, sleeves, neckline: one allowed value or nothing
        v = str(s.get(attr) or "").lower().strip()
        v = VALUE_ALIASES.get(v, v) or None
        if v and v not in ALLOWED[attr]:
            c = _closest(v, ALLOWED[attr], cutoff=0.75)
            notes.append(f"{attr}: “{v}” → {c or 'dropped'}"); v = c
        s[attr] = v
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
    s["month"] = _month(s.get("month"))
    s["weather"] = _valid_weather(s.get("weather"))
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
    it["stage"] = stage if stage in (1, 2, 3, 4, 5) else (3 if stage == 6 else 1)   # 6 is only for support / other
    it["spelling"] = [dict(typed=str(f.get("typed", "")), meant=str(f.get("meant", ""))) for f in (it.get("spelling") or [])
                      if isinstance(f, dict) and f.get("typed") and f.get("meant") and str(f["typed"]).lower() != str(f["meant"]).lower()]
    it["interpretation"] = str(it.get("interpretation") or "").strip()
    it["mappings"] = [m for m in (it.get("mappings") or []) if isinstance(m, dict) and m.get("phrase")]
    return it, notes


def understand(query, api_key, models, history=None, previous=None):
    """Run the intent agent with model fallback, then validate; returns (intent, model_used, log)."""
    log = []
    out, used = None, "offline rules"
    if api_key:
        for model in model_order(models):
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
def _month(v):
    """'January', 'jan', 1 -> 'january'; anything else -> None."""
    v = str(v or "").strip().lower()
    if v.isdigit() and 1 <= int(v) <= 12: return MONTHS[int(v) - 1]
    return next((m for m in MONTHS if v and (v == m or v == m[:3])), None)


CLIMATES = ("cold", "cool", "mild", "warm", "hot", "humid")


def _valid_weather(w):
    """The AI's weather estimate for the place and month: {climate, temp_c, note}, or None."""
    if not isinstance(w, dict) or str(w.get("climate") or "").lower() not in CLIMATES:
        return None
    try:
        t = int(round(float(w.get("temp_c")))) if w.get("temp_c") not in (None, "") else None
    except (TypeError, ValueError):
        t = None
    return dict(climate=str(w["climate"]).lower(), temp_c=t if t is None or -30 <= t <= 50 else None,
                note=str(w.get("note") or "").strip()[:80])


def occasion_tool(occasion, time_):
    if not occasion: return None
    return OCCASION_RULES.get((occasion, time_ or "day"))


def enrich(intent):
    """Context: the AI's weather estimate for the place and month, and occasion rules, add soft preferences."""
    soft = intent.setdefault("soft", {})
    calls = []
    w = soft.get("weather")
    if soft.get("city"):
        when = (soft.get("month") or datetime.date.today().strftime("%B")).title()
        temp = f", about {w['temp_c']}°C" if w and w.get("temp_c") is not None else ""
        calls.append(("weather (AI estimate)", f"{soft['city']}, {when}",
                      f"{w['note'] or w['climate']}{temp} in {when}" if w else "not estimated"))
    soft["climate"] = w["climate"] if w else None
    clothes = intent.get("hard", {}).get("category") in (None, "fashion")
    # which fabrics suit the weather is the AI's call (soft.fabrics); code only ranks warm layers first when it's cold
    if w and w["climate"] in ("cold", "cool") and clothes:
        types = intent.get("hard", {}).get("types") or []
        if not types:   # no product named: warm layers rank first, nothing is filtered out
            soft["prefer_types"] = WARM_LAYERS
        elif not any(t in WARM_LAYERS for t in types):   # "t-shirts for Manali": keep the t-shirts, suggest a warm layer
            soft["layer_tip"] = True
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
    for attr in STYLE_ATTRS:   # None = the listing doesn't say (allowed, ranked lower)
        if s.get(attr):
            ok = (p[attr] in _style_ok_values(attr, s[attr])) if p.get(attr) else None
            checks.append((_style_label(attr, s[attr]), ok, p.get(attr) or "not stated"))
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
_BRAND, _BRAND_M = _coded("brand")
_STYLE = {a: _coded(a) for a in STYLE_ATTRS}   # fit / pattern / sleeve / neck -> (codes, mapping)
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
    for attr in STYLE_ATTRS:
        if s.get(attr):
            codes, mapping = _STYLE[attr]
            out.append(_isin(codes, mapping, _style_ok_values(attr, s[attr]) + [""]))
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


# weakest first (solution doc: colour shade, fabric, pairing, style words); occasion type is near-hard, so it goes late;
# needs (fragrance-free, warm light) last, so a home or beauty search shows close options rather than nothing
RELAX_ORDER = ["colours", "colour_family", "fabrics", "neck", "sleeve", "fit", "pattern", "pairs", "time", "occasion", "needs"]


def search(intent, min_results=2, max_results=6):
    """Catalog search + verifier loop with constraint relaxation."""
    h, s = intent.get("hard", {}), dict(intent.get("soft", {}))
    s0 = dict(s)   # what the shopper asked for, before any relaxing
    relaxed, trace = [], []
    base = _hard_mask(h)
    exact = None
    prefer = _isin(_CFAM, _CFAM_M, s.get("prefer_colour_family") or [])
    prefer_t = _isin(_TYP, _TYP_M, s.get("prefer_types") or [])
    for attempt in range(len(RELAX_ORDER) + 1):
        ok = _all(_soft_masks(s), base)
        n_scored = int(ok.sum())
        if exact is None:
            exact = ok.copy()   # products that meet every original constraint
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
    for attr in STYLE_ATTRS:   # listings that say "floral" / "sleeveless" rank above ones that don't say, whatever the rating
        if s.get(attr):
            codes, mapping = _STYLE[attr]
            unknown = unknown + (codes == mapping.get("", -1)) * 0.5
    score = _RATING + prefer * 0.5 + prefer_t * 1.0 + _JITTER - unknown
    if relaxed:
        n_exact = int(exact.sum())
        score = score + exact * 2.0   # exact matches always rank above the close options added by relaxing
        trace.append(f"Exact matches before relaxing: {n_exact}" + (" (kept first)" if n_exact else ""))
    chosen = _top(np.flatnonzero(ok), score, max_results, per_brand=2)
    near = []
    if not len(chosen):  # show near misses on hard constraints, e.g. over budget: the cheapest few
        idx = np.flatnonzero(_hard_mask(h, drop=("budget",)))
        near = [_PL[i] for i in idx[np.argsort(_PRICE[idx], kind="stable")][:3]]
    # checks are against what the shopper asked for, so a relaxed constraint shows as ✕ on the close options
    return [(_PL[i], check_soft(_PL[i], s0)) for i in chosen], relaxed, trace, near


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


# ------------------------------------------------------------------ personal suggestions (profiles)
def recommend(prefs, gender=None, exclude=(), k=8):
    """'Picked for you': score the catalog against what a profile bought and searched for.
    prefs: dict field -> {value: weight} for fields type, colour_family, brand, occasion."""
    score = np.zeros(_N)
    for field, codes, mapping in (("type", _TYP, _TYP_M), ("colour_family", _CFAM, _CFAM_M), ("brand", _BRAND, _BRAND_M)):
        for v, w in (prefs.get(field) or {}).items():
            if v in mapping: score += (codes == mapping[v]) * float(w) * {"type": 1.0, "colour_family": 0.4, "brand": 0.6}[field]
    for v, w in (prefs.get("occasion") or {}).items():
        if v in _OCC_M: score += _OCC_M[v] * float(w) * 0.5
    ok = score > 0
    if gender in ("women", "men"):
        ok &= (_GEN == _GEN_M.get(gender, -1)) | (_GEN == _GEN_M.get("unisex", -1))
    for pid in exclude:
        ok[[i for i, p in enumerate(_PL) if p["id"] == pid]] = False
    return [_PL[i] for i in _top(np.flatnonzero(ok), score + _RATING + _JITTER, k, per_brand=2)]


# Look builder preview: what usually goes with each type, from types this catalog actually has
# (no footwear or jewellery here, so pairings stay within clothing)
PAIRS_WITH = {"kurta": ["palazzo", "dupatta", "leggings"], "kurta set": ["dupatta"], "anarkali set": ["dupatta"],
              "lehenga": ["dupatta"], "salwar suit": ["dupatta"], "saree": [], "palazzo": ["kurta"],
              "shirt": ["trousers", "jeans", "blazer"], "t-shirt": ["jeans", "shorts", "jacket"], "top": ["jeans", "skirt", "trousers"],
              "dress": ["jacket"], "jeans": ["t-shirt", "shirt", "top"], "trousers": ["shirt", "t-shirt"], "shorts": ["t-shirt"],
              "skirt": ["top"], "blazer": ["shirt", "trousers"], "jacket": ["t-shirt", "jeans"], "sweatshirt": ["jeans", "trousers"],
              "kurta pyjama": ["nehru jacket"], "nehru jacket": ["kurta set", "kurta"], "sherwani": [], "jumpsuit": ["jacket"]}


def complete_look(p, k=4):
    """Items that go with p: a matching type, same gender (or unisex), neutral or same colour family, at most 1.5x its price."""
    types = PAIRS_WITH.get(p["type"], [])
    if p["category"] != "fashion" or not types:
        return []
    m = _isin(_TYP, _TYP_M, types) & (_PRICE <= max(p["price"] * 1.5, 500))
    if p["gender"] in ("women", "men"):
        m &= (_GEN == _GEN_M.get(p["gender"], -1)) | (_GEN == _GEN_M.get("unisex", -1))
    match = _isin(_CFAM, _CFAM_M, ["neutral", p["colour_family"]])
    m &= np.array([q["id"] != p["id"] for q in _PL])
    # one of each pairing type first, matching colours preferred
    score = match * 1.0 + _RATING + _JITTER
    out = []
    for t in types:
        idx = np.flatnonzero(m & (_TYP == _TYP_M.get(t, -1)))
        out += [_PL[i] for i in _top(idx, score, 2, per_brand=1)]
    return out[:k]


LABEL_PROMPT = build_label_prompt(ALLOWED["types"])


def read_image(image_bytes, mime, api_key, models):
    """Read a size tag, bill or product label with Gemini vision. Returns (data, model, log); data is None on failure."""
    log = []
    if not api_key:
        return None, None, ["Reading photos needs AI mode (GEMINI_API_KEY)"]
    body = {"contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_bytes).decode()}},
                {"text": LABEL_PROMPT}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}}
    for model in model_order(models):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            r = _post_logged("read photo", model, url, body)
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code}: {r.text[:150]}")
            d = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            size = str(d.get("size") or "").upper().strip()
            d["size"] = size if size in SIZE_ORDER else None
            waist = re.sub(r"\D", "", str(d.get("waist") or ""))
            d["waist"] = waist if waist in WAIST_ORDER else None
            d["product_type"] = _closest(d["product_type"], ALLOWED["types"]) if d.get("product_type") else None
            d["gender"] = _closest(d["gender"], ALLOWED["gender"]) if d.get("gender") else None
            d["brand"] = (str(d.get("brand")).strip() or None) if d.get("brand") else None
            log.append(f"{model}: ok")
            return d, model, log
        except Exception as e:
            log.append(f"{model}: {str(e)[:90]}")
    return None, None, log


# ------------------------------------------------------------------ product Q&A (preview)
def _product_facts(p):
    fit = {-1: "runs small", 0: "true to size", 1: "runs large"}.get(p.get("fit_signal"), "unknown")
    return {"name": p["name"], "brand": p["brand"], "type": p["type"], "price_inr": p["price"], "colour": p["colour"],
            "fabric": p["fabric"] or "not stated", "occasions": p["occasions"], "sizes": p["sizes"],
            "fit_from_reviews": fit if p["category"] == "fashion" else "n/a",
            "notes": p["notes"], "reviews": p["reviews"]}


def _answer_offline(p, q):
    """Rule-based answers from the listing, used when there is no model."""
    ql, blob = q.lower(), " ".join(p["notes"] + p["reviews"]).lower()
    notes = lambda *words: [n for n in p["notes"] + p["reviews"] if any(w in n.lower() for w in words)]
    if any(w in ql for w in ("see-through", "see through", "sheer", "transparent", "lining")):
        hit = notes("sheer", "see-through", "lining", "lined")
        return "; ".join(hit) if hit else "Nothing in the listing or review notes says it is sheer."
    if any(w in ql for w in ("size", "fit", "small", "large", "tight", "loose")):
        if p["category"] != "fashion": return "Size isn't a concern for this product."
        sig = {-1: "runs small, so consider one size up", 0: "fits true to size", 1: "runs large, so consider one size down"}[p["fit_signal"]]
        hit = notes("small", "large", "tight", "loose", "size", "fit")
        return f"Fit reviews say it {sig}." + (f" Notes: {'; '.join(hit[:2])}." if hit else "")
    if any(w in ql for w in ("wash", "care", "clean", "iron", "crease")):
        hit = notes("wash", "clean", "crease", "steam", "iron")
        return "; ".join(hit) if hit else "The listing doesn't give care instructions."
    if any(w in ql for w in ("fabric", "material", "breathable", "humid", "summer", "hot", "cotton", "made of")):
        if not p["fabric"]: return "The listing doesn't state the fabric."
        airy = p["fabric"] in BREATHABLE
        return f"It's {p['fabric']}" + (", a breathable fabric that suits warm or humid weather." if airy else ".")
    if any(w in ql for w in ("colour", "color", "shade", "look like")):
        hit = notes("colour", "color", "peach", "pink", "shade", "light")
        return f"Listed colour: {p['colour']}." + (f" Reviews: {'; '.join(hit[:2])}." if hit else "")
    if any(w in ql for w in ("wedding", "office", "party", "occasion", "wear it", "haldi", "festive")):
        return f"It's suited to: {', '.join(p['occasions'])}."
    if any(w in ql for w in ("price", "cost", "discount", "offer")):
        return f"It costs ₹{p['price']:,}."
    return "I can only answer from this listing's details and review notes, and they don't cover that yet."


def ask_product(p, question, api_key, models):
    """Answer a shopper's question about one product from its listing and reviews only. Returns (answer, source)."""
    if not api_key:
        return _answer_offline(p, question), "listing (offline rules)"
    prompt = ("You answer a shopper's question about ONE product on an Indian fashion store. Use only the product data below "
              "(listing details, fit signal and review notes). If the data doesn't answer it, say so in one sentence and suggest "
              "what the shopper could check; never invent facts, measurements, policies or delivery dates. Reply in at most "
              "2 short sentences, in the shopper's language.\n\nProduct data: " + json.dumps(_product_facts(p), ensure_ascii=False)
              + "\n\nShopper's question: " + question)
    for model in model_order(models):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            r = _post_logged("product question", model, url, {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                                               "generationConfig": {"temperature": 0.2}})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip(), model
        except Exception:
            pass
    return _answer_offline(p, question), "listing (AI unavailable)"


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


# words shoppers use interchangeably; a normal search for one also matches the others
KW_SYNONYMS = {"kurti": ["kurti", "kurta"], "kurta": ["kurta", "kurti"], "pyjama": ["pyjama", "pajama"],
               "trousers": ["trouser", "pant", "chino"], "pant": ["pant", "trouser"], "jogger": ["jogger", "track"],
               "lehenga": ["lehenga", "lehnga"], "saree": ["saree", "sari"], "tshirt": ["tshirt", "tee"]}


_KW_STOP = {"for", "the", "and", "with", "in", "of", "an", "to", "my", "me", "some", "size", "buy", "show", "want", "need", "new", "best"}


def keyword_search(query, max_results=8, gender=None, info=None):
    """Normal search. Every meaningful word must match ("green tshirt" = green AND t-shirt; a colour also accepts close
    shades), falling back to partial matches only if nothing matches all of them. gender (from the shopper's profile)
    keeps fashion results to that gender + unisex, unless the query names a gender itself."""
    toks = _kw_tokens(query) - _KW_STOP
    size = SIZE_RE.search(query)
    hits = np.zeros(_N)
    every = np.ones(_N, bool)
    used, unknown = [], []
    for t in toks:
        variants = COLOUR_SYNONYMS.get(t) or KW_SYNONYMS.get(t) or [t]
        posts = [_KW_INDEX[v] for v in {_kw_stem(w) for w in variants} if v in _KW_INDEX]
        if not posts:
            unknown.append(t)
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
        info.update(words=used, mode=mode, gender=g, unknown=unknown)
    return [_PL[i] for i in _top(np.flatnonzero(ok), hits + _RATING + _JITTER, max_results, per_brand=3)]


def why_this(p, intent):
    s = intent.get("soft", {})
    bits = []
    if p["fabric"] in BREATHABLE and (s.get("fabrics") or s.get("city")) and s.get("climate") not in ("cold", "cool"):
        bits.append(f"breathable {p['fabric']}")
    if s.get("climate") in ("cold", "cool") and (p["fabric"] in WARM or p["type"] in WARM_LAYERS):
        where = (s.get("city") or "").title() + (f" in {s['month'].title()}" if s.get("month") else "")
        bits.append(f"warm {p['fabric'] or p['type']}" + (f" for {where.strip()}" if where.strip() else ""))
    if s.get("colours") and _colour_ok(p, s["colours"]):
        bits.append(f"in {p['colour']}")
    if s.get("colour_family") and p["colour_family"] in s["colour_family"]:
        bits.append(f"{p['colour']} suits {s.get('time') or 'the'} {s.get('occasion') or 'look'}".replace("the look", "the look"))
    for attr in STYLE_ATTRS:
        if s.get(attr) and p.get(attr) in _style_ok_values(attr, s[attr]):
            bits.append(f"{p[attr]} print" if attr == "pattern" and p[attr] not in ("solid", "embroidered", "self design") else
                        f"{p[attr]} fit" if attr == "fit" else p[attr])
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
def brand_offset(brand):
    return ANCHOR_BRANDS.get(brand or "", 0) or 0


def our_size(brand, size):
    """The brand's size label -> our size (Zara runs small: Zara M -> our S)."""
    if size not in SIZE_ORDER: return size
    return SIZE_ORDER[max(0, min(len(SIZE_ORDER) - 1, SIZE_ORDER.index(size) + brand_offset(brand)))]


def brand_size(brand, size):
    """Our size -> the brand's label for it (our M -> Zara L)."""
    if size not in SIZE_ORDER: return size
    return SIZE_ORDER[max(0, min(len(SIZE_ORDER) - 1, SIZE_ORDER.index(size) - brand_offset(brand)))]


def brand_note(brand):
    """'Zara runs small' / 'Marks & Spencer runs large' / standard / unknown, for captions and reasons."""
    if not brand or brand == "None / not sure": return ""
    if brand not in ANCHOR_BRANDS: return f"we don't have {brand}'s size data yet, so its sizes count as standard"
    return {-1: f"{brand} runs small", 1: f"{brand} runs large"}.get(brand_offset(brand), f"{brand} sizes are standard")


def _scale(p):
    return WAIST_ORDER if p["sizes"][0].isdigit() else SIZE_ORDER


def _return_bounds(scale, profile, ptype=None):
    """The shopper's own returns on this size scale: 'returned · too small' in 30 means 32 or up; 'too loose' in 34 means 32 or down.
    Returns (floor_idx, ceil_idx, note) or (None, None, None)."""
    floor, ceil, notes = None, None, []
    for o in profile.get("orders", []) or []:
        out, size = o.get("outcome", ""), str(o.get("size", ""))
        if not out.startswith("returned") or size not in scale:
            continue
        otype = PRODUCTS[o["pid"]]["type"] if o.get("pid") in PRODUCTS else None
        if ptype and otype and not _type_match([otype], ptype) and not _type_match([ptype], otype):
            continue   # a kurta returned in S says nothing about t-shirts
        what = f"a {otype} in {size}" if otype else f"a {size}"
        i = scale.index(size)
        if "small" in out or "tight" in out:
            floor = max(floor if floor is not None else -1, i + 1); notes.append(f"you returned {what} for being too small")
        elif any(w in out for w in ("loose", "big", "large")):
            ceil = min(ceil if ceil is not None else len(scale), i - 1); notes.append(f"you returned {what} for being too loose")
    return floor, ceil, "; ".join(notes) or None


def fit_agent(p, profile):
    """Size recommendation with confidence. profile: usual_size, waist, anchor_brand, anchor_size, past_brands, orders.
    The shopper's own returns (past orders) bound the recommendation: a size they sent back as too small is never suggested."""
    if p["category"] != "fashion" or p["sizes"] == ["Free"]:
        return None
    scale = _scale(p)
    brand = profile.get("anchor_brand") if profile.get("anchor_brand") != "None / not sure" else None
    anchored = bool(brand and profile.get("anchor_size"))   # a size only counts as an anchor while its brand is set
    base = (profile.get("anchor_size") if anchored else None) or profile.get("usual_size")
    source = f"your {brand} {base}" if anchored else f"your usual size {base}"
    if p["sizes"][0].isdigit():
        base = profile.get("waist") or None
        source = f"your waist {base}"
    floor, ceil, ret_note = _return_bounds(scale, profile, p["type"])
    from_returns = False
    if (not base or base not in scale) and ret_note:   # no size given, but their returns say where they are
        j = floor if floor is not None else ceil
        if 0 <= j < len(scale):
            base, from_returns = scale[j], True
    if not base or base not in scale:
        return dict(size=None, confidence="low", reason="No size history or anchor for you yet",
                    ask="Which brand fits you best, and in what size?")
    idx = scale.index(base)
    offset = brand_offset(brand) if anchored and not p["sizes"][0].isdigit() else 0   # brand sizing applies to S/M/L labels
    adj = -p["fit_signal"]  # runs small (-1) -> size up (+1)
    rec_idx = max(0, min(len(scale) - 1, idx + offset + adj))
    clamped = False
    if floor is not None and rec_idx < floor: rec_idx, clamped = min(floor, len(scale) - 1), True
    if ceil is not None and rec_idx > ceil: rec_idx, clamped = max(ceil, 0), True
    rec = scale[rec_idx]
    has_anchor = bool(profile.get("anchor_brand") and profile.get("anchor_brand") != "None / not sure") or p["brand"] in profile.get("past_brands", [])
    if p["brand"] in profile.get("past_brands", []) and p["fit_reviews"] >= 20:
        conf = "high"
    elif p["fit_reviews"] >= 40 and has_anchor:
        conf = "high"
    elif p["fit_reviews"] >= 20 or has_anchor or from_returns:
        conf = "medium"
    else:
        conf = "low"
    signal = {-1: "runs small", 0: "true to size", 1: "runs large"}[p["fit_signal"]]
    if from_returns:   # e.g. "you returned a 30 for being too small, so we start from 32; 12 reviews say it runs small, so 34"
        reason = f"{ret_note[0].upper()}{ret_note[1:]}, so we start from {base}; {p['fit_reviews']} reviews say it {signal}" + \
                 (f", so {rec}" if rec != base else "")
    else:
        reason = f"Based on {source}"
        if offset:   # e.g. "your Zara M (Zara runs small: Zara M ≈ our S)"
            reason += f" ({brand_note(brand)}: {brand} {base} ≈ our {scale[max(0, min(len(scale) - 1, idx + offset))]})"
        reason += f"; {p['fit_reviews']} reviews mention fit: {signal}"
        if adj and not clamped: reason += f", so size {'up' if adj > 0 else 'down'} to {rec}"
        if ret_note and clamped: reason += f"; {ret_note}, so {rec}"
    if clamped and conf == "high":   # your returns override the size you gave us: say so, don't sound certain
        conf = "medium"
    note = signal
    if ret_note and clamped and not from_returns:   # shown on the card badge: "M recommended · you returned a kurta in S"
        note = ret_note.split("; ")[0].replace(" for being too small", "").replace(" for being too loose", "")
    ask = "Which brand fits you best, and in what size?" if conf == "low" or from_returns else None
    if rec not in p["sizes"]:
        return dict(size=None, confidence="low", reason=f"Your likely size {rec} is not stocked", ask=None)
    return dict(size=rec, confidence=conf, reason=reason, ask=ask, simulated=bool(p.get("fit_sim")), note=note, base=base,
                from_returns=bool(ret_note and (from_returns or clamped)))


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
