"""Saved answers for the live demo script (🎬 Demo tab), so the demo runs the same way every time.

Each search step holds the answer the intent agent gives for that request: the same JSON shape Gemini returns under the
response schema, and it goes through the same validator, tools, search, verifier and fit layer as a live answer. Only the
model call is skipped. The AI trace labels these "demo script", so a saved answer is never shown as a live one.
A follow-up step only applies right after the step it refines; anything typed off-script goes to the live AI as usual.
"""
import re

_STOP = set("i im am a an the in for and with me my to show some please which that go goes going we are is it this of on "
            "do does will would can".split())
_SAME = {"tshirts": "tshirt", "tshirt": "tshirt", "tees": "tshirt", "tee": "tshirt", "vlue": "blue", "flowers": "floral",
         "flower": "floral", "flowery": "floral", "floral": "floral", "outfit": "outfits", "clothes": "outfits",
         "shade": "shades", "jan": "january", "sweatshirt": "sweatshirts", "jacket": "jackets", "mens": "men", "womens": "women",
         "jewellery": "jewelry", "seethrough": "see", "through": "see"}


def norm(text):
    """Words that matter, so small differences in typing ("T-shirts &", "tshirts and") still match a step."""
    t = re.sub(r"\(refers to result[^)]*\)", " ", (text or "").lower())
    t = re.sub(r"t-shirts?", "tshirt", t).replace("see-through", "see through").replace("₹", " ")
    words = [_SAME.get(w, w) for w in re.findall(r"[a-z0-9]+", t)]
    return frozenset(w for w in words if w not in _STOP and w != "000")


def _intent(interpretation, hard=None, soft=None, stage=3, confidence="high", mappings=(), clarify=None, spelling=()):
    h = dict(category="fashion", gender=None, budget_min=None, budget_max=None, size=None, types=[], style=None)
    s = dict(occasion=None, time=None, city=None, month=None, weather=None, colour_family=[], colours=[], fabrics=[],
             fabric_named=False, fit=None, pattern=None, sleeve=None, neck=None, pairs=None, needs=[])
    h.update(hard or {}); s.update(soft or {})
    return dict(query_type="product_search", reply=None, confidence=confidence, spelling=list(spelling), stage=stage,
                interpretation=interpretation, hard=h, soft=s, clarify=clarify,
                mappings=[dict(phrase=p, maps_to=m) for p, m in mappings])


JAIPUR_OCT = dict(climate="warm", temp_c=32, note="warm, sunny days and pleasant evenings")
JAIPUR_JAN = dict(climate="cold", temp_c=9, note="cold mornings and nights, mild afternoons")

# id, the step it refines (None = a new search), what the presenter may type, the agent's answer
SEARCHES = [
    dict(id="jaipur", prev=None, says=["Outfits for Jaipur", "clothes for Jaipur", "outfits for a Jaipur trip"],
         answer=_intent("Outfits for a trip to Jaipur: warm in October, so light, breathable fabrics",
                        soft=dict(occasion="casual", city="jaipur", month="october", weather=JAIPUR_OCT, fabrics=["cotton", "linen"]),
                        mappings=[("Jaipur", "city Jaipur; no month given, so this month (October): warm, about 32°C"),
                                  ("warm weather", "breathable fabrics: cotton, linen")])),
    dict(id="jaipur_jan", prev="jaipur", says=["tshirts & I am going in January", "tshirts, I am going in January",
                                               "t-shirts I am going in January", "tshirts going in january", "tshirts in january"],
         answer=_intent("T-shirts for Jaipur in January: cold mornings and nights, so long sleeves in warmer fabrics",
                        hard=dict(types=["t-shirt"], style="western"),
                        soft=dict(occasion="casual", city="jaipur", month="january", weather=JAIPUR_JAN,
                                  fabrics=["fleece", "wool", "acrylic"], sleeve="long sleeves"),
                        mappings=[("tshirts", "item: t-shirt, kept as asked"),
                                  ("going in January", "month January: Jaipur is cold then (about 9°C at night), "
                                                       "so warm fabrics replace cotton and linen, and long sleeves")])),
    dict(id="jaipur_layer", prev="jaipur_jan", says=["Add a warm layer: jackets & sweatshirts", "add a warm layer",
                                                    "jackets & sweatshirts", "show me jackets and sweatshirts"],
         answer=_intent("A warm layer for Jaipur in January: sweatshirts, jackets and sweaters",
                        hard=dict(types=["sweatshirt", "jacket", "sweater"], style="western"),
                        soft=dict(occasion="casual", city="jaipur", month="january", weather=JAIPUR_JAN,
                                  fabrics=["fleece", "wool", "acrylic"]),
                        mappings=[("warm layer", "items: sweatshirts, jackets, sweaters in warm fabrics")])),
    dict(id="maldives", prev=None, says=["Maldives Outfits", "outfits for Maldives", "Maldives trip outfits", "clothes for Maldives"],
         answer=_intent("Holiday outfits for the Maldives: hot and humid, so light, breathable, bright beachwear",
                        hard=dict(style="western"),
                        soft=dict(occasion="casual", city="maldives", month="october",
                                  weather=dict(climate="humid", temp_c=30, note="hot and humid beach weather"),
                                  fabrics=["cotton", "linen", "rayon"], colour_family=["bright"]),
                        mappings=[("Maldives", "beach holiday, hot and humid (about 30°C): breathable fabrics, bright colours")])),
    dict(id="maldives_blue", prev="maldives", says=["vlue tops with flower under 700", "blue tops with flower under 700",
                                                   "blue floral tops under 700", "blue tops with flowers under 700"],
         answer=_intent("Blue floral tops under ₹700 for the Maldives trip",
                        hard=dict(types=["top"], budget_max=700, style="western"),
                        soft=dict(colours=["blue"], pattern="floral"),
                        spelling=[dict(typed="vlue", meant="blue")],
                        mappings=[("vlue", "spelling: blue"), ("with flower", "print: floral"), ("under 700", "budget under ₹700")])),
    dict(id="marriage", prev=None, says=["Marriage outfits", "outfits for marriage", "marriage outfit", "wedding outfits"],
         answer=_intent("Outfits for a wedding (ethnic or western not said)", stage=4, confidence="medium",
                        soft=dict(occasion="wedding"),
                        mappings=[("marriage", "occasion: wedding")],
                        clarify=dict(question="Ethnic or western for the wedding?", options=["Ethnic", "Western", "Show both"]))),
    dict(id="marriage_ethnic", prev=None, says=["Marriage outfits — Ethnic", "ethnic marriage outfits", "ethnic wedding outfits"],
         answer=_intent("Ethnic outfits for a wedding", hard=dict(style="ethnic"), soft=dict(occasion="wedding"),
                        mappings=[("Ethnic", "your answer: style ethnic")])),
    dict(id="marriage_gold", prev="marriage_ethnic", says=["dark shades which go with gold", "dark shades that go with gold",
                                                           "dark colours that go with gold", "dark shades with gold"],
         answer=_intent("Ethnic wedding outfits in dark shades that pair with gold jewellery",
                        hard=dict(style="ethnic"), soft=dict(occasion="wedding", colour_family=["dark"], pairs="gold"),
                        mappings=[("dark shades", "colour family: dark"), ("go with gold", "pairs with gold jewellery")])),
    dict(id="jaggu", prev=None, says=["outfits for jaggu", "outfit for jaggu", "clothes for jaggu"],
         answer=_intent("Outfits for Jaggu (a person's name, so men's or women's isn't clear)", stage=4, confidence="medium",
                        mappings=[("Jaggu", "a name: shopping for someone else, gender not known")],
                        clarify=dict(question="Is Jaggu a man or a woman?", options=["Men", "Women"]))),
    dict(id="jaggu_men", prev=None, says=["outfits for jaggu — Men", "men outfits for jaggu"],
         answer=_intent("Men's outfits for Jaggu", hard=dict(gender="men"), mappings=[("Men", "your answer: gender men")])),
    dict(id="jaggu_women", prev=None, says=["outfits for jaggu — Women", "women outfits for jaggu"],
         answer=_intent("Women's outfits for Jaggu", hard=dict(gender="women"), mappings=[("Women", "your answer: gender women")])),
    dict(id="mumbai", prev=None,
         says=["I need a breathable, pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs well with silver jewelry",
               "breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs with silver jewellery"],
         answer=_intent("Breathable pastel ethnic outfit for a humid daytime wedding in Mumbai, under ₹6,000, to wear with silver",
                        hard=dict(gender="women", budget_max=6000, style="ethnic", types=["kurta", "kurta set", "anarkali set", "salwar suit"]),
                        soft=dict(occasion="wedding", time="day", city="mumbai", month="october",
                                  weather=dict(climate="humid", temp_c=31, note="hot and humid"),
                                  colour_family=["pastel"], fabrics=["cotton", "linen", "rayon", "khadi", "chanderi"], pairs="silver"),
                        mappings=[("breathable", "fabrics: cotton, linen, rayon, khadi, chanderi"), ("pastel", "colour family: pastel"),
                                  ("humid daytime wedding in Mumbai", "occasion wedding, daytime; Mumbai is humid (about 31°C)"),
                                  ("pairs well with silver jewelry", "pairs with: silver"), ("under ₹6,000", "budget under ₹6,000")])),
]

_BY_WORDS = {}
for _s in SEARCHES:
    for _say in _s["says"]:
        _BY_WORDS[(_s["prev"], norm(_say))] = _s


def find(query, prev_step=None):
    """The saved step for this query: a follow-up step only right after the step it refines."""
    words = norm(query)
    return _BY_WORDS.get((prev_step, words)) if prev_step else _BY_WORDS.get((None, words))


def question_key(q):
    return norm(q)


# Product questions: (product id, the question) -> answer written only from that listing's text
_SEE = "is this see-through"
QA = {
    ("Y10188713", norm(_SEE)): "The listing doesn't say it's sheer, and it doesn't mention a lining or name the fabric. It's a light "
                               "beige embroidered kurta, so in bright daylight a nude or beige slip underneath is the safe choice.",
    ("Y10185205", norm(_SEE)): "The listing doesn't mention sheerness or a lining, and doesn't name the fabric. It's off-white, so a "
                               "skin-tone slip underneath is the safe choice for a daytime event.",
    ("Y10172905", norm(_SEE)): "Nothing in the listing says it's sheer, but it doesn't mention a lining or the fabric either. "
                               "The beige base is light, so a slip underneath is the safe choice in daylight.",
    ("Y10260187", norm(_SEE)): "No. It's a fleece-lined hooded sweatshirt, so it isn't see-through.",
}

# Photos (md5 of the file) -> what the label reader returns; the sample tag is data/demo/sample_size_tag.png
SAMPLE_TAG = "data/demo/sample_size_tag.png"
PHOTOS = {
    "cf1723a48f081499af92cd72461eda36": dict(kind="size tag", summary="A Roadster size tag: size M, women's top, 100% cotton",
                                             brand="Roadster", product_type="top", size="M", waist=None, colour=None,
                                             gender="women", price=None),
}


def answer(pid, q):
    words = norm(q)
    return QA.get((pid, words)) or QA.get(("*", words))
