"""Build data/myntra_catalog.csv.gz from the raw Kaggle Myntra export.

    python build_catalog.py [raw.csv.gz] [out.csv.gz]

Input : data/myntra_fashion_products.csv.gz  (Kaggle: nirokey/myntra-fashion-products; columns
        name, sku, mpn, price, in_stock, currency, brand, description, images, gender)
Output: a compact, cleaned file with the attributes SearchSense needs.

The raw data has NO ratings, sizes, MRP/discount, colour or fabric. What this script does about that:
  * colour, colour_family, fabric, type, style, occasions, time, pairs are DERIVED from the product title and
    description with keyword rules (approximate; good enough for a demo, not ground truth).
  * sizes and fit_signal / fit_reviews are SIMULATED (deterministic per product) and flagged fit_sim=1.
    They exist so the fit agent has something to reason about. They are not real shopper data.
  * rating and MRP are left empty rather than invented.
Standard library only, so it runs anywhere the app does.
"""
import csv, gzip, hashlib, re, sys, collections

RAW = "data/myntra_fashion_products.csv.gz"
OUT = "data/myntra_catalog.csv.gz"
MAX_PER_TYPE = 700          # keep the catalog balanced; the biggest types (shirts, kurtas) are capped
MAX_PER_BRAND_TYPE = 60     # stop one brand flooding a type

# --------------------------------------------------------------------------- types
# (regex on lowercased title, type, category, style). First match wins; order matters.
TYPE_RULES = [
    # excluded first: things the demo does not model (footwear, bags, jewellery, innerwear, kids' sizes...)
    (r"\b(bra|bras|briefs?|boxers?|panty|panties|innerwear|night ?suit|nightdress|night ?wear|lounge|camisole|"
     r"thermal|socks?|stole|scarf|muffler|belt|wallet|bag|backpack|handbag|clutch|duffel|trolley|"
     r"shoes?|sneakers?|sandals?|flats?|heels?|loafers?|boots?|flip-flops?|slippers?|juttis?|mojaris?|derbys?|"
     r"watch|sunglasses|earrings?|necklace|bracelet|bangles?|ring|rings|pendant|jewellery|anklet|"
     r"cap|hat|gloves?|tie|cufflinks?|pocket square|mask|towel|helmet)\b", None, None, None),
    # lifestyle (home)
    (r"\b(curtains?)\b", "curtain", "lifestyle", "minimal"),
    (r"\b(bedsheets?|bed ?sheet|comforter|duvet|blanket|quilt|dohar)\b", "bedding", "lifestyle", "minimal"),
    (r"\b(cushion covers?|pillow covers?)\b", "cushion cover", "lifestyle", "boho"),
    (r"\b(placemats?|table runner|coasters?)\b", "table linen", "lifestyle", "minimal"),
    (r"\b(mug|mugs|tumbler|cups?)\b", "mug", "lifestyle", "minimal"),
    (r"\b(lamp|lamps)\b", "table lamp", "lifestyle", "minimal"),
    (r"\b(planter|with pot|vase|candle|diffuser|wall (art|decor|clock))\b", "home decor", "lifestyle", "minimal"),
    # personal care
    (r"\b(eau de (parfum|toilette)|perfume|fragrance|deodorant|body mist)\b", "perfume", "personal care", "beauty"),
    (r"\b(lipstick|lip gloss|lip liner|liquid lipstick)\b", "lipstick", "personal care", "beauty"),
    (r"\b(moisturi[sz]er|sunscreen|face wash|serum|face cream|body lotion)\b", "moisturiser", "personal care", "skincare"),
    (r"\b(blush|foundation|compact|kajal|eyeliner|mascara|eyeshadow|nail polish|highlighter|concealer|primer|bronzer)\b",
     "makeup", "personal care", "beauty"),
    # ethnic
    (r"\bsaree\b|\bsari\b", "saree", "fashion", "ethnic"),
    (r"\blehenga\b", "lehenga", "fashion", "ethnic"),
    (r"\banarkali\b", "anarkali set", "fashion", "ethnic"),
    (r"\bsharara\b|\bgharara\b", "sharara set", "fashion", "ethnic"),
    (r"\bsherwani\b", "sherwani", "fashion", "ethnic"),
    (r"\bnehru jacket\b|\bwaistcoat\b|\bethnic jacket\b", "nehru jacket", "fashion", "ethnic"),
    (r"\bdress material\b|\bsalwar\b|\bpatiala\b|\bchuridar\b(?! kurta)", "salwar suit", "fashion", "ethnic"),
    (r"\bkurtas? (with|&|and)\b|\bkurta sets?\b|\bkurtis? (with|&)\b|\bpyjama set\b|\bkurta pyjama\b", "kurta set", "fashion", "ethnic"),
    (r"\bkurtas?\b|\bkurtis?\b", "kurta", "fashion", "ethnic"),
    (r"\bpalazzos?\b", "palazzo", "fashion", "ethnic"),
    (r"\bdupatta\b", "dupatta", "fashion", "ethnic"),
    # western
    (r"\bco-?ords?\b|\bclothing set\b|\btop (with|&) (skirt|shorts|trousers|pants|palazzo)", "co-ord set", "fashion", "western"),
    (r"\bjumpsuit\b|\bplaysuit\b|\bdungarees?\b", "jumpsuit", "fashion", "western"),
    (r"\bjeans\b|\bjeggings\b", "jeans", "fashion", "western"),
    (r"\bleggings\b|\btreggings\b", "leggings", "fashion", "western"),
    (r"\b(trousers?|chinos?|track ?pants?|pants?|joggers?|cargos?|culottes?)\b", "trousers", "fashion", "western"),
    (r"\bshorts\b|\bbermudas?\b", "shorts", "fashion", "western"),
    (r"\bskirts?\b|\bskorts?\b", "skirt", "fashion", "western"),
    (r"\b(dress|gown|maxi|midi)\b", "dress", "fashion", "western"),
    (r"\bt-?shirts?\b|\btees?\b|\bpolo\b", "t-shirt", "fashion", "western"),
    (r"\bsweatshirts?\b|\bhoodies?\b", "sweatshirt", "fashion", "western"),
    (r"\bsweaters?\b|\bpullovers?\b|\bcardigans?\b", "sweater", "fashion", "western"),
    (r"\bblazers?\b|\bsuits?\b|\bcoats?\b", "blazer", "fashion", "western"),
    (r"\bjackets?\b|\bshrug\b|\bwindcheater\b|\bgilet\b|\bpuffer\b", "jacket", "fashion", "western"),
    (r"\bshirts?\b", "shirt", "fashion", "western"),
    (r"\b(tops?|blouse|tunic|tank|bodysuit|crop)\b", "top", "fashion", "western"),
]
TYPE_RULES = [(re.compile(r, re.I), t, c, s) for r, t, c, s in TYPE_RULES]

# --------------------------------------------------------------------------- colours
# word -> (canonical colour, family, swatch hex)
_C = {}
def _reg(words, family, hexv):
    for w in words.split(","):
        _C[w.strip()] = (w.strip(), family, hexv)
_reg("white", "neutral", "#F7F7F2"); _reg("off-white,off white,cream,ivory,beige,nude,skin", "pastel", "#F3EBDD")
_reg("grey,gray,silver,charcoal,steel,khaki,tan,taupe,camel,metallic", "neutral", "#B8B9C0")
_reg("blue", "neutral", "#6C8EBF"); _reg("sky blue,baby blue,powder blue,light blue,ice blue", "pastel", "#BFD7F2")
_reg("navy,navy blue,teal,peacock blue,indigo,midnight", "dark", "#24305E"); _reg("turquoise,turquoise blue,aqua,cyan", "bright", "#3CC7C0")
_reg("black", "dark", "#2B2B2B"); _reg("brown,coffee,chocolate,mocha,rust,copper,bronze,mahogany", "dark", "#7A5230")
_reg("maroon,burgundy,wine,plum,mauve,magenta", "dark", "#7A1F2B"); _reg("olive,olive green,bottle green,forest green,army green,sea green,teal green", "dark", "#5A6B3A")
_reg("purple,violet", "dark", "#5B3A8C"); _reg("lavender,lilac,mint,mint green,peach,baby pink,rose,blush,pastel,powder,light pink,pista,pista green,lemon", "pastel", "#D9C8F0")
_reg("pink", "pastel", "#F4B8CC"); _reg("green,lime,lime green,parrot green,neon green,sea green", "bright", "#3FAE6A")
_reg("red,orange,yellow,mustard,gold,fuchsia,coral,hot pink,rani,saffron,multi,multicoloured,multicolour", "bright", "#E8473B")
_SWATCH_FIX = {"peach": "#F8CBAD", "mint": "#B9E2CF", "mint green": "#B9E2CF", "lavender": "#D9C8F0", "lilac": "#D9C8F0", "yellow": "#F7E37A",
               "mustard": "#D7A928", "orange": "#F28C3A", "red": "#D93A3A", "gold": "#C9A44C", "green": "#3FAE6A", "olive": "#6B7A3A",
               "maroon": "#7A1F2B", "burgundy": "#7A1F2B", "rose": "#F2A9BC", "fuchsia": "#D62A82", "coral": "#F57F6C", "lime green": "#A6D12A",
               "teal": "#1F7A7A", "navy": "#24305E", "navy blue": "#24305E", "grey": "#9EA0A8", "black": "#2B2B2B", "brown": "#7A5230",
               "multi": "#C9A4D8", "multicoloured": "#C9A4D8", "multicolour": "#C9A4D8", "lemon": "#F7E37A"}
_C = {k: (c, f, _SWATCH_FIX.get(c, h)) for k, (c, f, h) in _C.items()}
_C["lemon"] = ("lemon", "bright", "#F7E37A")
_COLOUR_RE = re.compile(r"(?<![a-z])(" + "|".join(sorted((re.escape(k) for k in _C), key=len, reverse=True)) + r")(?:-colou?red|-toned)?(?![a-z])")
SKIP_BEFORE = re.compile(r"^.*?\b(women|men|unisex|girls|boys)\b", re.I)

# --------------------------------------------------------------------------- fabric
FABRIC_RULES = [  # (regex on lowercase title+description, canonical)
    (r"\bchanderi\b", "chanderi"), (r"\bkhadi\b", "khadi"), (r"\bmul (cotton|mul)\b", "mul cotton"),
    (r"\bcotton[- ]silk\b|\bsilk[- ]cotton\b", "cotton-silk"), (r"\blinen\b", "linen"),
    (r"\bdenim\b|\bjeans\b", "denim"), (r"\bvelvet\b", "velvet"), (r"\bbrocade\b", "brocade"), (r"\bgeorgette\b", "georgette"),
    (r"\bchiffon\b", "chiffon"), (r"\bsatin\b", "satin"), (r"\bsilk\b|\bkanjeevaram\b|\bbanarasi\b", "silk"),
    (r"\brayon\b|\bviscose\b", "rayon"), (r"\bcrepe\b", "crepe"), (r"\bnet\b", "net"), (r"\bwool\b|\bwoollen\b", "wool"),
    (r"\bfleece\b", "fleece"), (r"\bleather\b|\bfaux leather\b", "leather"), (r"\bnylon\b", "nylon"),
    (r"\bacrylic\b", "acrylic"), (r"\bpolyester\b", "polyester"), (r"\bcotton\b", "cotton"),
    (r"\bceramic\b", "ceramic"), (r"\bglass\b", "glass"),
]
FABRIC_RULES = [(re.compile(r, re.I), f) for r, f in FABRIC_RULES]

# --------------------------------------------------------------------------- occasions / time / pairs
EVENING_WORDS = re.compile(r"velvet|sequin|embellish|zari|brocade|bandhgala|sherwani|gown|cocktail|party|evening|satin|"
                           r"banarasi|kanjeevaram|net\b|stone|beads?", re.I)
FESTIVE_WORDS = re.compile(r"embroider|zari|woven design|gotta|banarasi|kanjeevaram|bandhani|printed straight kurta|"
                           r"anarkali|sequin|mirror|foil|festive|ethnic motif|kalamkari|bagh|ikat|block print", re.I)
WEDDING_TYPES = {"saree", "lehenga", "anarkali set", "sharara set", "sherwani", "nehru jacket", "kurta set", "salwar suit"}
FORMAL_WORDS = re.compile(r"formal|slim fit.*(shirt|trousers)|checked formal|pinstripe|blazer", re.I)
CASUAL_WORDS = re.compile(r"casual|t-?shirt|polo|jeans|hoodie|sweatshirt|joggers|track|denim|shorts|cargo", re.I)
PARTY_WORDS = re.compile(r"party|sequin|bodycon|cocktail|off-?shoulder|bardot|gown|velvet|satin|embellish", re.I)
SLIM_FIT = re.compile(r"\bslim\b|skinny|bodycon|tapered|fitted|super skinny", re.I)
LOOSE_FIT = re.compile(r"relaxed|loose|oversized|baggy|boxy|a-line|flared|flare|straight kurta|regular fit", re.I)

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
WAIST_ORDER = ["26", "28", "30", "32", "34", "36"]
SIZED_TYPES_ALPHA = {"kurta", "kurta set", "anarkali set", "sharara set", "salwar suit", "dress", "t-shirt", "shirt", "top", "sweatshirt",
                     "sweater", "jacket", "blazer", "jumpsuit", "co-ord set", "nehru jacket", "sherwani", "palazzo", "leggings",
                     "skirt", "shorts"}
SIZED_TYPES_WAIST = {"jeans", "trousers"}
FREE_SIZE_TYPES = {"saree", "lehenga", "dupatta"}  # sold free-size / unstitched in this demo


def h(*parts):
    """Deterministic 0..1 float from strings (keeps simulated data stable across builds)."""
    d = hashlib.md5("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(d[:6], "big") / float(1 << 48)


def clean(s):
    s = re.sub(r"\s+", " ", (s or "").replace("nbsp;", " ")).strip()
    return s


def classify(name):
    for rx, t, c, s in TYPE_RULES:
        if rx.search(name):
            return (t, c, s) if t else None   # t is None for the excluded types
    return None


def colours(name, desc):
    """Colour words from the title after the gender token (title format: Brand Gender Colour... Type)."""
    m = SKIP_BEFORE.match(name)
    body = name[m.end():] if m else name
    found = [_C[x.lower()] for x in _COLOUR_RE.findall(body.lower())]
    if not found:  # fall back to the first sentence of the description ("Black and grey printed ...")
        first = re.split(r"[,.]", desc.lower())[0]
        found = [_C[x] for x in _COLOUR_RE.findall(first)]
    uniq, seen = [], set()
    for c in found:
        if c[0] not in seen:
            uniq.append(c); seen.add(c[0])
    return uniq[:2]


SPORTS_WORDS = re.compile(r"\b(running|training|gym|sports?|workout|yoga|athletic|active ?wear|track ?pants?|joggers?|"
                          r"jogging|cycling|football|tennis|badminton|cricket)\b", re.I)
QUICK_DRY = re.compile(r"rapid[- ]?dry|quick[- ]?dry|dri[- ]?fit|dry ?cell|drycell|wicks?|wicking|dries fast|sweat[- ]absorb", re.I)


def fabric(name, desc, t):
    text = f"{name.lower()} {desc.lower()}"
    for rx, f in FABRIC_RULES:
        if rx.search(text):
            return f
    if t == "jeans":
        return "denim"
    # performance fabric named only by its technology ("Rapid Dry technology wicks sweat")
    return "quick-dry" if QUICK_DRY.search(text) else ""


def derive(row):
    name, desc = clean(row["name"]), clean(row["description"])
    brand = clean(row["brand"])
    # classify on the title without the brand, so "Louis Philippe Jeans ... Shirt" is a shirt, not jeans
    title = name[len(brand):].strip() if brand and name.lower().startswith(brand.lower()) else name
    cls = classify(title)
    if not cls:
        return None
    t, cat, style = cls
    gender = {"Women": "women", "Men": "men"}.get(row["gender"], "unisex")
    cols = colours(title, desc)
    if len(cols) == 2 and cols[0][1] != cols[1][1] and cols[0][1] == "dark":
        pass
    colour = " & ".join(c[0] for c in cols) if cols else ("" if cat == "personal care" else "multi")
    fam = cols[0][1] if cols else "neutral"
    if cols and (cols[0][0].startswith("multi") or (len(cols) == 2 and {cols[0][1], cols[1][1]} == {"bright", "dark"})):
        fam = "bright" if cols[0][0].startswith("multi") else fam
    swatch = cols[0][2] if cols else "#D8D9E0"
    fab = fabric(title, desc, t)
    text = f"{title} {desc[:300]}"
    lt = text.lower()

    # occasions
    occ = []
    if cat == "fashion":
        if t in WEDDING_TYPES and FESTIVE_WORDS.search(lt) or t in {"saree", "lehenga", "anarkali set", "sharara set", "sherwani"}:
            occ += ["wedding", "festive"]
        if t in {"kurta", "kurta set", "salwar suit", "nehru jacket", "palazzo", "dupatta"}:
            occ += ["festive"] if "festive" not in occ else []
            # everyday kurtas: unless the listing reads as evening / heavy wear, it suits casual and office days.
            # (Most listings don't state a fabric, so an unknown fabric must not rule this out.)
            heavy = EVENING_WORDS.search(lt) or fab in ("velvet", "silk", "brocade", "satin", "net", "georgette")
            if not heavy:
                occ += ["casual", "office"]
            if FESTIVE_WORDS.search(lt) and "wedding" not in occ and fam in ("pastel", "bright"):
                occ += ["wedding"]
        # haldi / mehendi: daytime ethnic wear in bright or pastel colours, not heavy evening fabrics
        if t in WEDDING_TYPES | {"kurta", "palazzo", "dupatta"} and "haldi" not in occ and t not in {"sherwani", "nehru jacket"}:
            heavy = EVENING_WORDS.search(lt) or fab in ("velvet", "silk", "brocade", "satin", "net")
            if ("yellow" in colour or fam in ("bright", "pastel")) and not heavy:
                occ += ["haldi"]
        if t in {"dress", "jumpsuit", "co-ord set", "skirt", "top"}:
            occ += ["casual", "brunch"]
            if PARTY_WORDS.search(lt): occ += ["party"]
            if fam in ("pastel", "bright") and t == "dress" and "floral" in lt: occ += ["wedding"]
        if t in {"shirt", "trousers", "blazer"}:
            occ += ["office"] if FORMAL_WORDS.search(lt) or t == "blazer" else ["casual", "office"]
            if t == "shirt" and fab == "linen": occ += ["brunch"]
        if t in {"jeans"}: occ += ["casual", "office"]
        if t in {"t-shirt", "sweatshirt", "sweater", "jacket", "shorts", "leggings"}:
            occ += ["casual"]
        if t == "blazer" and PARTY_WORDS.search(lt): occ += ["party"]
        if t in {"sherwani", "nehru jacket"}: occ += ["party"]
    elif cat == "lifestyle":
        occ = ["home"]
    else:
        occ = ["daily"]
    if t in {"t-shirt", "shorts", "trousers", "sweatshirt", "jacket", "leggings", "top"} and SPORTS_WORDS.search(f"{title} {desc}"):
        occ += ["sports"]
    occ = list(dict.fromkeys(occ)) or ["casual"]

    # time of day
    if cat != "fashion":
        tm = "any"
    elif t in {"jeans", "trousers", "t-shirt", "sweatshirt", "sweater", "jacket", "blazer", "leggings", "shorts", "shirt", "top", "skirt", "jumpsuit", "co-ord set"}:
        tm = "any" if t in {"jeans", "trousers", "jacket", "blazer", "sweater", "sweatshirt"} else "day"
        if PARTY_WORDS.search(lt) and tm != "any": tm = "evening"
    elif EVENING_WORDS.search(lt) or fam == "dark" and t in {"saree", "lehenga", "anarkali set", "sherwani", "sharara set"}:
        tm = "evening"
    else:
        tm = "day"
    if fab in ("velvet", "wool", "fleece") and cat == "fashion": tm = "evening" if t not in {"jacket", "sweater", "sweatshirt"} else "any"

    # silver/gold pairing
    if re.search(r"gold|zari|golden|copper|bronze|mustard", lt):
        pairs = "gold"
    elif fam in ("pastel", "neutral") or any(w in colour for w in ("blue", "grey", "silver", "white", "mint", "lilac", "lavender")):
        pairs = "silver" if t in WEDDING_TYPES | {"dress", "top", "palazzo", "dupatta"} else "any"
    else:
        pairs = "any"

    # honest notes only from phrases actually in the description
    notes = []
    for rx, msg in ((r"\bsheer\b|see-?through|transparent", "Description mentions a sheer / see-through fabric"),
                    (r"\bdry[- ]clean\b", "Dry clean only"), (r"hand[- ]?wash", "Hand wash recommended"),
                    (r"\bunstitched\b", "Contains an unstitched piece"), (r"\bslim fit\b|skinny", "Slim fit: may run snug"),
                    (r"\boversized\b|relaxed fit|loose fit", "Relaxed or loose fit")):
        if re.search(rx, lt) and msg not in notes:
            notes.append(msg)
    if QUICK_DRY.search(f"{title} {desc}"):
        notes.append("Quick-dry / sweat-wicking fabric (per description)")

    # simulated sizes + fit signal (flagged fit_sim=1 in the output)
    if cat == "fashion" and t in SIZED_TYPES_ALPHA:
        start = int(h(row["sku"], "s0") * 2)            # starts XS or S
        n = 4 + int(h(row["sku"], "sn") * 3)             # 4..6 sizes
        sizes = SIZE_ORDER[start:start + n]
    elif cat == "fashion" and t in SIZED_TYPES_WAIST:
        start = int(h(row["sku"], "w0") * 2)
        sizes = WAIST_ORDER[start:start + 5]
    elif cat == "personal care":
        m = re.search(r"(\d+(?:\.\d+)?)\s?(ml|g)\b", title.lower())
        sizes = [f"{m.group(1)} {m.group(2)}"] if m else ["Free"]
    else:
        sizes = ["Free"]
    fit_sim = 1 if sizes != ["Free"] and cat == "fashion" else 0
    r = h(row["sku"], "fit")
    if SLIM_FIT.search(lt): sig = -1 if r < 0.55 else 0
    elif LOOSE_FIT.search(lt): sig = 1 if r < 0.3 else 0
    else: sig = -1 if r < 0.12 else (1 if r > 0.9 else 0)
    fit_reviews = int(5 + (h(row["sku"], "fr") ** 2) * 110) if fit_sim else 0

    imgs = (row["images"] or "").split(" ~ ")
    image = imgs[0].strip().replace("http://", "https://") if imgs and imgs[0].strip() else ""
    try:
        price = int(row["price"])
    except ValueError:
        return None
    return dict(id="Y" + str(row["sku"]), name=name, brand=clean(row["brand"]), gender=gender, category=cat, type=t, style=style,
                colour=colour, colour_family=fam, fabric=fab, price=price, occasions="|".join(occ), time=tm, pairs=pairs,
                sizes="|".join(sizes), fit_signal=sig, fit_reviews=fit_reviews, fit_sim=fit_sim, swatch=swatch, image=image,
                notes="|".join(notes))


FIELDS = ["id", "name", "brand", "gender", "category", "type", "style", "colour", "colour_family", "fabric", "price", "occasions",
          "time", "pairs", "sizes", "fit_signal", "fit_reviews", "fit_sim", "swatch", "image", "notes"]


def build(raw=RAW, out=OUT):
    rows, seen_names = [], set()
    stats = collections.Counter()
    with gzip.open(raw, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            stats["raw"] += 1
            if row["gender"] not in ("Women", "Men", "Unisex"):
                stats["dropped: kids"] += 1; continue
            if row["in_stock"].strip().lower() != "true":
                stats["dropped: out of stock"] += 1; continue
            key = clean(row["name"]).lower()
            if key in seen_names:
                stats["dropped: duplicate name"] += 1; continue
            seen_names.add(key)
            d = derive(row)
            if not d:
                stats["dropped: type not modelled (footwear, bags, jewellery, innerwear...)"] += 1; continue
            if d["price"] < 99:
                stats["dropped: price"] += 1; continue
            rows.append(d)
    # balance: cap per type and per (brand, type), cheapest-hash order so the sample is stable but unbiased
    rows.sort(key=lambda d: h(d["id"], "order"))
    per_type, per_bt, kept = collections.Counter(), collections.Counter(), []
    for d in rows:
        if per_type[d["type"]] >= MAX_PER_TYPE or per_bt[(d["brand"], d["type"])] >= MAX_PER_BRAND_TYPE:
            stats["dropped: balancing cap"] += 1; continue
        per_type[d["type"]] += 1; per_bt[(d["brand"], d["type"])] += 1; kept.append(d)
    kept.sort(key=lambda d: d["id"])
    with gzip.open(out, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(kept)
    return kept, stats


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else RAW
    out = sys.argv[2] if len(sys.argv) > 2 else OUT
    kept, stats = build(raw, out)
    print(f"wrote {len(kept)} rows to {out}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    for field in ("category", "gender", "style", "type", "colour_family", "fabric", "time"):
        print(field, dict(collections.Counter(d[field] for d in kept).most_common(40)))
