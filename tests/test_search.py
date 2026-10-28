"""Regression checks for the search stack. Run: python tests/test_search.py  (or pytest tests/)."""
import os, random, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import agent as A
from catalog import PRODUCTS, CATALOG_SOURCE


def run(q, gender=None):
    r = A.route(q)
    if r["stage"] == 6: return r, None, None
    if r["stage"] in (0, 2): return r, A.keyword_search(r["query"]), None
    intent, _, _ = A.understand(r["query"], None, [], [])
    if gender: intent["hard"]["gender"] = gender
    intent, _ = A.enrich(intent)
    return r, [p for p, _ in A.search(intent)[0]], intent


def test_catalog_loaded():
    assert len(PRODUCTS) > 1000, CATALOG_SOURCE
    assert {"F01", "M01", "L01", "C01"} <= set(PRODUCTS)          # curated demo products are kept
    myntra = [p for p in PRODUCTS.values() if p["source"] == "myntra"]
    assert all(p["rating"] is None and p["mrp"] is None for p in myntra)   # nothing invented
    assert all(p["fit_sim"] for p in myntra if p["category"] == "fashion" and p["sizes"] != ["Free"])


def test_scenarios():
    r, items, _ = run("wite linnen shirt M")
    assert r["stage"] == 2 and items[0]["id"] == "M01"
    _, items, it = run("breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery", "women")
    assert {"F01", "F02", "F03", "F04"} <= {p["id"] for p in items} and all(p["price"] <= 6000 for p in items)
    _, items, _ = run("high-waist straight jeans for office", "women")
    assert items[0]["id"] == "F11" and all(p["type"] == "jeans" for p in items)
    _, items, it = run("outfit for a wedding", "women")
    assert it["stage"] == 4 and it["clarify"] and items
    _, items, it = run("chanderi lehenga for a day wedding under ₹6,000", "women")
    assert items[0]["id"] == "F05" and all(p["type"] == "lehenga" and p["price"] <= 6000 for p in items)
    _, items, _ = run("minimal table lamp for a small reading corner, warm light, under 2500")
    assert [p["id"] for p in items] == ["L01"]
    _, items, _ = run("fragrance-free moisturiser for oily acne-prone skin that sits well under sunscreen under 800")
    assert [p["id"] for p in items] == ["C01"]
    assert run("where is my order")[0]["stage"] == 6


def test_spelling_aliases():
    for q, want in [("sari", "saree"), ("Sari", "saree"), ("lengha", "lehenga"), ("tshirt M", "t-shirt M"), ("wite linnen shirt M", "white linen shirt M")]:
        r = A.route(q)
        assert r["stage"] == 2 and r["query"] == want, (q, r)
    assert all(p["type"] == "saree" for p in A.keyword_search("saree"))
    assert all(p["type"] == "t-shirt" for p in A.keyword_search("t-shirt"))


def test_browse():
    ids = A.browse()
    assert len(ids) == len(PRODUCTS) == len(set(ids))
    assert sum(PRODUCTS[i]["source"] == "demo" for i in ids[:24]) <= 4      # real listings lead the home page
    assert all(PRODUCTS[i]["style"] == "ethnic" for i in A.browse("Ethnic"))
    prices = [PRODUCTS[i]["price"] for i in A.browse("Women", "kurta", "Price: low to high")]
    assert prices == sorted(prices) and prices


def test_followup_uses_previous_search_only():
    priya = "breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery"
    hist = ["fragrance-free moisturiser for oily skin -> x", priya + " -> y"]
    it, _, _ = A.understand("#2 but cheaper budget under 3298", None, [], hist)
    assert it["hard"]["category"] == "fashion" and it["hard"]["budget_max"] == 3298 and it["hard"]["style"] == "ethnic"


def test_keyword_search_needs_every_word():
    items = A.keyword_search("green t-shirt", 24)
    assert items and all(p["type"] == "t-shirt" and any(w in p["colour"] for w in A.colour_targets("green")) for p in items)
    men = A.keyword_search("t-shirt", 24, gender="men")
    assert men and all(p["gender"] in ("men", "unisex") for p in men)


def test_routing_support_and_purpose():
    for q in ["Return Order", "where is my order", "refund not received", "cancel my order", "talk to an agent", "coupon not working"]:
        assert A.route(q)["stage"] == 6, q
    for q in ["track pants for men", "returnable kurta", "exchange offer saree", "green tshirt"]:
        assert A.route(q)["stage"] != 6, q
    for q in ["Tshirt for Gym & Runnig", "kurta for office", "hi", "iphone 15"]:
        assert A.route(q)["stage"] == "agent", q
    assert A.route("Tshirt for Gym & Runnig")["fixes"] == []          # "Gym" is no longer "corrected" to "gm"


def test_validator_repairs_model_output():
    it, notes = A.validate_intent({"query_type": "product_search", "stage": 3, "interpretation": "x",
                                   "hard": {"category": "Fashion", "gender": "male", "types": ["tshirt", "gym wear"], "budget_max": "1,500"},
                                   "soft": {"occasion": "gym", "fabrics": ["dri-fit"], "colours": ["greenish"], "needs": ["oily skin"]}})
    assert it["hard"]["gender"] == "men" and it["hard"]["types"] == ["t-shirt"] and it["hard"]["budget_max"] == 1500
    assert it["soft"]["occasion"] == "sports" and it["soft"]["fabrics"] == ["quick-dry"] and it["soft"]["colours"] == ["green"]
    assert it["soft"]["needs"] == []   # skin needs dropped on a fashion search
    sup, _ = A.validate_intent({"query_type": "support", "reply": "Taking you to Customer Care.", "stage": 3,
                                "hard": {"types": ["kurta"]}, "soft": {"colours": ["red"]}})
    assert sup["stage"] == 6 and sup["hard"]["types"] == [] and sup["soft"]["colours"] == [] and sup["reply"]


def test_gym_finds_quick_dry_tees():
    it = A.validate_intent({"query_type": "product_search", "stage": 3, "interpretation": "gym tee",
                            "hard": {"category": "fashion", "gender": "men", "types": ["t-shirt"]},
                            "soft": {"occasion": "sports", "fabrics": [], "fabric_named": False}})[0]
    it, _ = A.enrich(it)
    assert {"polyester", "quick-dry"} <= set(it["soft"]["fabrics"])   # added by the occasion rule
    items = [p for p, _ in A.search(it, max_results=8)[0]]
    assert items and all(p["gender"] in ("men", "unisex") and "sports" in p["occasions"] for p in items)
    assert items[0]["fabric"] in ("quick-dry", "polyester", "nylon")   # stated performance fabric ranks first


def test_prompt_and_schema():
    import json
    for t in A.ALLOWED["types"]:
        assert t in A.SYSTEM
    for k in ("query_type", "support", "out_of_catalog", "Previous search constraints"):
        assert k in A.SYSTEM
    json.dumps(A.RESPONSE_SCHEMA)
    assert A.RESPONSE_SCHEMA["properties"]["query_type"]["enum"] == ["product_search", "out_of_catalog", "support", "other"]


def test_fit_uses_own_returns():
    returned_small = dict(usual_size="M", orders=[dict(size="30", outcome="returned · too small at the waist")])
    fa = A.fit_agent(A.PRODUCTS["F12"], returned_small)              # true-to-size jeans
    assert fa["size"] == "32" and fa["confidence"] == "medium" and "returned a 30" in fa["reason"]
    fa = A.fit_agent(A.PRODUCTS["F12"], dict(waist="30", orders=returned_small["orders"]))
    assert fa["size"] == "32"                                          # never the size they sent back as too small
    assert A.fit_agent(A.PRODUCTS["F12"], dict(usual_size="M"))["size"] is None   # no history: no guess


def test_complete_the_look():
    look = A.complete_look(A.PRODUCTS["F11"])                          # women's jeans
    assert look and all(p["type"] in A.PAIRS_WITH["jeans"] and p["gender"] in ("women", "unisex") for p in look)
    assert A.complete_look(A.PRODUCTS["L01"]) == []                   # not clothing


def test_vectorised_search_matches_reference():
    random.seed(1)
    types, fabs = sorted(A._TYP_M), [f for f in A._FAB_M if f]
    for _ in range(60):
        h = dict(category=random.choice([None, "fashion", "lifestyle"]), gender=random.choice([None, "women", "men"]),
                 budget_max=random.choice([None, 800, 3000]), budget_min=random.choice([None, None, 500]), size=random.choice([None, "M", "32"]),
                 types=random.sample(types, random.choice([0, 1, 2])), style=random.choice([None, "ethnic", "western"]))
        s = dict(occasion=random.choice([None, "wedding", "office"]), time=random.choice([None, "day", "evening"]),
                 colours=random.sample(["lilac", "navy blue", "white", "pink", "mustard"], random.choice([0, 0, 1])),
                 fabric_named=random.choice([True, False]),
                 colour_family=random.sample(["pastel", "dark", "neutral"], random.choice([0, 1])), fabrics=random.sample(fabs, random.choice([0, 2])),
                 pairs=random.choice([None, "silver"]), needs=[])
        ref = np.array([A._hard_ok(p, h)[0] for p in A._PL])
        assert (A._hard_mask(h) == ref).all(), h
        soft = A._all(A._soft_masks(s), A._hard_mask(h))
        # a check passes unless it is False (None = not stated in the listing, allowed for inferred fabrics)
        assert (soft == np.array([r and all(c[1] is not False for c in A.check_soft(p, s)) for r, p in zip(ref, A._PL)])).all(), s


def test_fast():
    t = time.time()
    for q in ["breathable pastel ethnic outfit for a humid daytime wedding under 6000", "outfit for a wedding", "jeans for office"]:
        run(q, "women")
    for q in ["kurta", "white shirt M", "dres", "lipstick"]:
        run(q)
    assert time.time() - t < 1.0


def test_falls_back_to_demo_catalog():
    code = "import catalog; assert len(catalog.PRODUCTS) == 24 and 'demo only' in catalog.CATALOG_SOURCE; import agent; print('ok')"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         env=dict(os.environ, SEARCHSENSE_CATALOG="/nonexistent.csv.gz"))
    assert out.stdout.strip() == "ok", out.stderr[-400:]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok ", name)
