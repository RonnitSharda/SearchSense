"""Catalog for the SearchSense MVP.

* 25 hand-written demo products (illustrative: prices, reviews and fit data are made up). They keep the
  scripted demo scenarios reliable.
* ~5k real Myntra product listings loaded from data/myntra_catalog.csv.gz (built by build_catalog.py from the
  Kaggle dataset nirokey/myntra-fashion-products). Title, brand, price, image URL and gender are real; type, colour,
  fabric, style, occasion, time and pairing are derived from the title/description with keyword rules; sizes and
  fit signals are SIMULATED (no ratings, MRP or fit reviews exist in the source data).
If the data file is missing the app falls back to the 25 demo products only.
"""
import csv, gzip, os

BREATHABLE = {"cotton", "linen", "chanderi", "mul cotton", "khadi", "cotton-silk", "rayon"}
HEAVY = {"velvet", "silk", "brocade", "georgette", "denim", "polyester"}

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
WAIST_ORDER = ["26", "28", "30", "32", "34", "36"]

# fit_signal: -1 runs small, 0 true to size, +1 runs large ; fit_reviews = reviews that mention fit
P = [
 # ---------- Women's ethnic ----------
 dict(id="F01", name="Blush chanderi anarkali set", brand="Kaavya", gender="women", category="fashion", type="anarkali set", style="ethnic",
      colour="blush pink", colour_family="pastel", fabric="chanderi", price=5499, occasions=["wedding", "festive"], time="day",
      pairs="silver", sizes=SIZE_ORDER[1:5], fit_signal=0, fit_reviews=64, rating=4.5, swatch="#F4B8CC",
      notes=["Lining included; not see-through", "Soft pink reads slightly peach in warm light"],
      reviews=["Perfect for a day wedding, very light", "True to size, took my usual M", "Colour is a little more peach than pink"]),
 dict(id="F02", name="Mint cotton kurta & palazzo", brand="Rangsutra", gender="women", category="fashion", type="kurta set", style="ethnic",
      colour="mint green", colour_family="pastel", fabric="cotton", price=3299, occasions=["wedding", "haldi", "festive", "casual"], time="day",
      pairs="silver", sizes=SIZE_ORDER[0:5], fit_signal=-1, fit_reviews=88, rating=4.3, swatch="#B9E2CF",
      notes=["Runs small at the waist", "Breathable; fine for humid weather"],
      reviews=["Runs small, size up", "So comfortable in Mumbai heat", "Waist is tight, exchanged for L"]),
 dict(id="F03", name="Lilac linen kurta set with dupatta", brand="Oorja", gender="women", category="fashion", type="kurta set", style="ethnic",
      colour="lilac", colour_family="pastel", fabric="linen", price=4699, occasions=["wedding", "festive", "office"], time="day",
      pairs="silver", sizes=SIZE_ORDER[1:6], fit_signal=0, fit_reviews=41, rating=4.4, swatch="#D9C8F0",
      notes=["Linen creases easily; steam before wearing"],
      reviews=["Lovely lilac, exactly like pictures", "Fits as expected", "Wrinkles a lot"]),
 dict(id="F04", name="Powder-blue mul cotton sharara set", brand="Kaavya", gender="women", category="fashion", type="sharara set", style="ethnic",
      colour="powder blue", colour_family="pastel", fabric="mul cotton", price=5899, occasions=["wedding", "festive"], time="day",
      pairs="silver", sizes=SIZE_ORDER[1:5], fit_signal=+1, fit_reviews=37, rating=4.2, swatch="#BFD7F2",
      notes=["Runs slightly large; flared fit", "Very soft, slightly sheer: wear a slip"],
      reviews=["Loose fit, could size down", "Breezy and light", "Bit sheer in sunlight"]),
 dict(id="F05", name="Peach cotton-silk lehenga set", brand="Nayaab", gender="women", category="fashion", type="lehenga", style="ethnic",
      colour="peach", colour_family="pastel", fabric="cotton-silk", price=5800, occasions=["wedding", "festive", "haldi"], time="day",
      pairs="gold", sizes=SIZE_ORDER[1:5], fit_signal=0, fit_reviews=29, rating=4.1, swatch="#F8CBAD",
      notes=["Gold zari border; pairs best with gold"],
      reviews=["Good fit", "Zari is gold-toned", "Light enough for a day function"]),
 dict(id="F06", name="Ivory chanderi lehenga with mirror work", brand="Nayaab", gender="women", category="fashion", type="lehenga", style="ethnic",
      colour="ivory", colour_family="pastel", fabric="chanderi", price=8999, occasions=["wedding", "festive"], time="day",
      pairs="silver", sizes=SIZE_ORDER[1:5], fit_signal=0, fit_reviews=22, rating=4.6, swatch="#F3EBDD",
      notes=["Mirror work is heavy on the skirt"],
      reviews=["Stunning", "True to size", "Skirt is heavier than it looks"]),
 dict(id="F07", name="Emerald velvet anarkali", brand="Shahi", gender="women", category="fashion", type="anarkali set", style="ethnic",
      colour="emerald", colour_family="dark", fabric="velvet", price=6999, occasions=["wedding", "party", "festive"], time="evening",
      pairs="gold", sizes=SIZE_ORDER[1:5], fit_signal=-1, fit_reviews=45, rating=4.4, swatch="#1F6B52",
      notes=["Warm fabric; best for winter evenings", "Runs small at the bust"],
      reviews=["Gorgeous for a winter sangeet", "Too warm for day", "Size up"]),
 dict(id="F08", name="Maroon silk saree with gold border", brand="Shahi", gender="women", category="fashion", type="saree", style="ethnic",
      colour="maroon", colour_family="dark", fabric="silk", price=7499, occasions=["wedding", "festive"], time="evening",
      pairs="gold", sizes=["Free"], fit_signal=0, fit_reviews=0, rating=4.7, swatch="#7A1F2B",
      notes=["Blouse piece unstitched"], reviews=["Rich colour", "Heavy drape"]),
 dict(id="F09", name="Lemon-yellow cotton kurta set", brand="Rangsutra", gender="women", category="fashion", type="kurta set", style="ethnic",
      colour="lemon yellow", colour_family="bright", fabric="cotton", price=2499, occasions=["haldi", "festive", "casual"], time="day",
      pairs="silver", sizes=SIZE_ORDER[0:5], fit_signal=0, fit_reviews=52, rating=4.2, swatch="#F7E37A",
      notes=["Bright yellow, as pictured"], reviews=["Perfect for haldi", "True to size"]),
 dict(id="F10", name="Sage cotton angrakha kurta", brand="Oorja", gender="women", category="fashion", type="kurta", style="ethnic",
      colour="sage green", colour_family="pastel", fabric="cotton", price=1899, occasions=["office", "casual"], time="day",
      pairs="silver", sizes=SIZE_ORDER[0:6], fit_signal=0, fit_reviews=33, rating=4.0, swatch="#C5D5B5",
      notes=["Kurta only; bottoms not included"], reviews=["Office favourite", "Nice fit"]),
 # ---------- Women's western ----------
 dict(id="F11", name="High-waist straight jeans, mid wash", brand="Denimco", gender="women", category="fashion", type="jeans", style="western",
      colour="mid blue", colour_family="neutral", fabric="denim", price=2299, occasions=["office", "casual"], time="any",
      pairs="any", sizes=WAIST_ORDER, fit_signal=-1, fit_reviews=12, rating=4.0, swatch="#6C8EBF",
      notes=["Runs small at the waist", "Rigid denim; little stretch"],
      reviews=["Size up one", "Snug at the waist", "Good length"]),
 dict(id="F12", name="High-waist straight jeans, black", brand="Urbane", gender="women", category="fashion", type="jeans", style="western",
      colour="black", colour_family="dark", fabric="denim", price=1999, occasions=["office", "casual"], time="any",
      pairs="any", sizes=WAIST_ORDER, fit_signal=0, fit_reviews=96, rating=4.3, swatch="#2B2B2B",
      notes=["Stretch denim"], reviews=["True to size", "Comfortable all day"]),
 dict(id="F13", name="Beige linen co-ord set", brand="Loom & Co", gender="women", category="fashion", type="co-ord set", style="western",
      colour="beige", colour_family="neutral", fabric="linen", price=2899, occasions=["office", "casual", "brunch"], time="day",
      pairs="any", sizes=SIZE_ORDER[0:5], fit_signal=+1, fit_reviews=58, rating=4.4, swatch="#E2D3B5",
      notes=["Relaxed fit; size down for a closer fit"], reviews=["Roomy", "Great for summer"]),
 dict(id="F14", name="Pastel floral midi dress", brand="Loom & Co", gender="women", category="fashion", type="dress", style="western",
      colour="pastel floral", colour_family="pastel", fabric="cotton", price=2599, occasions=["brunch", "casual", "wedding"], time="day",
      pairs="any", sizes=SIZE_ORDER[0:5], fit_signal=0, fit_reviews=40, rating=4.2, swatch="#F6D6E0",
      notes=["Slightly sheer; lined bodice only"], reviews=["Pretty", "Fits well"]),
 # ---------- Men ----------
 dict(id="M01", name="White linen shirt", brand="Loom & Co", gender="men", category="fashion", type="shirt", style="western",
      colour="white", colour_family="neutral", fabric="linen", price=1799, occasions=["office", "casual", "brunch"], time="day",
      pairs="any", sizes=SIZE_ORDER[1:6], fit_signal=0, fit_reviews=120, rating=4.5, swatch="#F7F7F2",
      notes=["Slightly see-through in bright light"], reviews=["Classic", "True to size"]),
 dict(id="M02", name="Sky-blue linen shirt", brand="Urbane", gender="men", category="fashion", type="shirt", style="western",
      colour="sky blue", colour_family="pastel", fabric="linen", price=1599, occasions=["office", "casual"], time="day",
      pairs="any", sizes=SIZE_ORDER[1:6], fit_signal=-1, fit_reviews=70, rating=4.2, swatch="#BFDDF5",
      notes=["Slim fit; runs small across the shoulders"], reviews=["Size up", "Nice colour"]),
 dict(id="M03", name="Ivory cotton kurta pyjama set", brand="Rangsutra", gender="men", category="fashion", type="kurta set", style="ethnic",
      colour="ivory", colour_family="pastel", fabric="cotton", price=2799, occasions=["wedding", "haldi", "festive"], time="day",
      pairs="any", sizes=SIZE_ORDER[1:6], fit_signal=0, fit_reviews=48, rating=4.4, swatch="#F3EBDD",
      notes=["Pyjama has a drawstring"], reviews=["Light and comfy", "Fits well"]),
 dict(id="M04", name="Navy silk nehru jacket", brand="Shahi", gender="men", category="fashion", type="nehru jacket", style="ethnic",
      colour="navy", colour_family="dark", fabric="silk", price=3499, occasions=["wedding", "party", "festive"], time="evening",
      pairs="any", sizes=SIZE_ORDER[1:6], fit_signal=-1, fit_reviews=31, rating=4.3, swatch="#24305E",
      notes=["Runs small; size up if layering"], reviews=["Smart", "Tight over a kurta"]),
 # ---------- Lifestyle ----------
 dict(id="L01", name="Brass dome table lamp", brand="Hearth", gender="unisex", category="lifestyle", type="table lamp", style="minimal",
      colour="brass", colour_family="neutral", fabric="brass", price=2399, occasions=["home"], time="any",
      pairs="any", sizes=["Height 38 cm"], fit_signal=0, fit_reviews=0, rating=4.4, swatch="#C9A44C",
      notes=["Warm 2700K bulb included", "Small footprint: fits a side table"], reviews=["Cosy light", "Compact"]),
 dict(id="L02", name="Ceramic bedside lamp, sage", brand="Hearth", gender="unisex", category="lifestyle", type="table lamp", style="minimal",
      colour="sage", colour_family="pastel", fabric="ceramic", price=1899, occasions=["home"], time="any",
      pairs="any", sizes=["Height 45 cm"], fit_signal=0, fit_reviews=0, rating=4.1, swatch="#C5D5B5",
      notes=["Cool white bulb; swap for warm light"], reviews=["Pretty", "Light is a bit cold"]),
 dict(id="L03", name="Jute cotton cushion covers (set of 2)", brand="Hearth", gender="unisex", category="lifestyle", type="cushion cover", style="boho",
      colour="natural", colour_family="neutral", fabric="cotton", price=899, occasions=["home"], time="any",
      pairs="any", sizes=["16x16 in"], fit_signal=0, fit_reviews=0, rating=4.0, swatch="#D8C7A3",
      notes=["Slightly rough texture"], reviews=["Earthy look"]),
 # ---------- Personal care ----------
 dict(id="C01", name="Oil-free gel moisturiser, fragrance-free", brand="Dermalab", gender="unisex", category="personal care", type="moisturiser", style="skincare",
      colour="clear", colour_family="neutral", fabric="gel", price=649, occasions=["daily"], time="any",
      pairs="any", sizes=["50 ml"], fit_signal=0, fit_reviews=0, rating=4.5, swatch="#DDEFF5",
      notes=["Non-comedogenic", "Sits well under sunscreen"], reviews=["Great for oily skin", "No pilling under SPF"]),
 dict(id="C02", name="Rich shea body cream", brand="Dermalab", gender="unisex", category="personal care", type="moisturiser", style="skincare",
      colour="cream", colour_family="neutral", fabric="cream", price=749, occasions=["daily"], time="any",
      pairs="any", sizes=["200 ml"], fit_signal=0, fit_reviews=0, rating=4.2, swatch="#F5EBDC",
      notes=["Contains fragrance", "Heavy texture: better for dry skin"], reviews=["Too heavy for oily skin"]),
 dict(id="C03", name="Niacinamide matte sunscreen SPF 50", brand="Sunveil", gender="unisex", category="personal care", type="sunscreen", style="skincare",
      colour="clear", colour_family="neutral", fabric="gel", price=599, occasions=["daily"], time="any",
      pairs="any", sizes=["50 g"], fit_signal=0, fit_reviews=0, rating=4.4, swatch="#FFF3C4",
      notes=["No white cast", "Mild fragrance"], reviews=["Matte finish", "Good for humid weather"]),
]

for _p in P:
    _p.update(source="demo", fit_sim=True, image="", mrp=None)   # demo fit data is illustrative too
PRODUCTS = {p["id"]: p for p in P}

DATA_FILE = os.environ.get("SEARCHSENSE_CATALOG") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "myntra_catalog.csv.gz")


def _load_myntra(path):
    out = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out.append(dict(
                id=r["id"], name=r["name"], brand=r["brand"], gender=r["gender"], category=r["category"], type=r["type"],
                style=r["style"], colour=r["colour"], colour_family=r["colour_family"], fabric=r["fabric"], price=int(r["price"]),
                occasions=r["occasions"].split("|"), time=r["time"], pairs=r["pairs"], sizes=r["sizes"].split("|"),
                fit_signal=int(r["fit_signal"]), fit_reviews=int(r["fit_reviews"]), fit_sim=r["fit_sim"] == "1",
                rating=None, mrp=None, swatch=r["swatch"], image=r["image"], notes=[n for n in r["notes"].split("|") if n],
                reviews=[], source="myntra"))
    return out


CATALOG_SOURCE = "demo only (data/myntra_catalog.csv.gz not found)"
if os.path.exists(DATA_FILE):
    try:
        _rows = _load_myntra(DATA_FILE)
        PRODUCTS.update({p["id"]: p for p in _rows})
        CATALOG_SOURCE = f"{len(P)} demo + {len(_rows):,} Myntra listings"
    except Exception as e:  # corrupt / partial file: never break the app
        CATALOG_SOURCE = f"demo only (could not read Myntra data: {str(e)[:60]})"

# Size anchors from other brands (illustrative brand-to-platform offsets)
# How a brand's labels compare with ours (illustrative): our size = the brand's size + offset.
# -1 = the brand runs small (a Zara M fits like our S); +1 = it runs large; 0 = standard. Brands not listed count as standard.
ANCHOR_BRANDS = {"Zara": -1, "H&M": 0, "Uniqlo": -1, "Mango": -1, "Levi's": 0, "Marks & Spencer": +1, "W": 0, "Biba": 0,
                 "FabIndia": +1, "Libas": 0, "Allen Solly": 0, "Roadster": 0, "None / not sure": None}

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]

WARM = {"wool", "fleece", "velvet", "acrylic"}            # fabrics for cold weather
WARM_LAYERS = ["jacket", "sweater", "sweatshirt", "blazer"]   # types to rank first when it's cold

OCCASION_RULES = {  # mocked occasion-rules tool
 ("wedding", "day"): dict(colour_family=["pastel"], fabric_pref="light", tip="Daytime weddings favour light fabrics and soft colours"),
 ("wedding", "evening"): dict(colour_family=["dark", "bright"], fabric_pref="any", tip="Evening weddings allow richer colours and fabrics"),
 ("haldi", "day"): dict(colour_family=["bright", "pastel"], fabric_pref="light", tip="Haldi favours yellow or pastel cotton"),
 ("office", "day"): dict(colour_family=["neutral", "pastel"], fabric_pref="light", tip="Office wear favours neutral, breathable pieces"),
 ("sports", "day"): dict(colour_family=[], fabric_pref="quick-dry", fabrics=["polyester", "nylon", "quick-dry"],
                         tip="Workouts favour quick-dry synthetics (polyester, nylon, dri-fit) over cotton, which stays wet"),
 ("sports", "evening"): dict(colour_family=[], fabric_pref="quick-dry", fabrics=["polyester", "nylon", "quick-dry"],
                             tip="Workouts favour quick-dry synthetics (polyester, nylon, dri-fit) over cotton, which stays wet"),
}
