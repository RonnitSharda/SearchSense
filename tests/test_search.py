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


def test_vectorised_search_matches_reference():
    random.seed(1)
    types, fabs = sorted(A._TYP_M), [f for f in A._FAB_M if f]
    for _ in range(60):
        h = dict(category=random.choice([None, "fashion", "lifestyle"]), gender=random.choice([None, "women", "men"]),
                 budget_max=random.choice([None, 800, 3000]), size=random.choice([None, "M", "32"]),
                 types=random.sample(types, random.choice([0, 1, 2])), style=random.choice([None, "ethnic", "western"]))
        s = dict(occasion=random.choice([None, "wedding", "office"]), time=random.choice([None, "day", "evening"]),
                 colour_family=random.sample(["pastel", "dark", "neutral"], random.choice([0, 1])), fabrics=random.sample(fabs, random.choice([0, 2])),
                 pairs=random.choice([None, "silver"]), needs=[])
        ref = np.array([A._hard_ok(p, h)[0] for p in A._PL])
        assert (A._hard_mask(h) == ref).all(), h
        soft = A._all(A._soft_masks(s), A._hard_mask(h))
        assert (soft == np.array([r and all(c[1] for c in A.check_soft(p, s)) for r, p in zip(ref, A._PL)])).all(), s


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
