"""Style attributes read from a listing's title and description: fit, print / pattern, sleeves and neckline.

Used by build_catalog.py (Myntra listings) and catalog.py (demo products). Keyword rules, so approximate: an empty value
means the listing doesn't say, and the search treats that as "unknown" (allowed, ranked below listings that state it).
The title wins over the description; the first rule that matches wins, so specific prints come before "printed".
"""
import re

FITS = ["relaxed", "regular", "slim"]
PATTERNS = ["floral", "polka dots", "striped", "checked", "geometric", "ethnic motifs", "abstract", "animal print", "tie-dye",
            "graphic", "embroidered", "colourblocked", "self design", "printed", "solid"]
SLEEVES = ["sleeveless", "short sleeves", "3/4 sleeves", "long sleeves"]
NECKS = ["v-neck", "round neck", "mandarin collar", "collar", "boat neck", "square neck", "sweetheart neck", "off-shoulder",
         "halter neck", "high neck"]
# a request for "printed" accepts any print; the others are exact
PRINTS = {"floral", "polka dots", "geometric", "ethnic motifs", "abstract", "animal print", "tie-dye", "graphic", "printed"}

_FIT = [("relaxed", r"\b(relaxed|loose|oversized|baggy|boyfriend|mom|comfort) fit\b|\bwide[- ]leg|\bflared\b|\boversized\b|\bboxy\b|\bpalazzos?\b"),
        ("slim", r"\b(slim|skinny|super skinny|tapered|muscle) fit\b|\bskinny\b|\bbodycon\b|\bslim\b"),
        ("regular", r"\b(regular|straight|classic) fit\b|\bstraight\b(?! hem)")]
_PATTERN = [("floral", r"\bfloral|\bflower"), ("polka dots", r"\bpolka"), ("striped", r"\bstriped?s?\b|\bpinstripe"),
            ("checked", r"\bcheck(ed|s)?\b|\bplaid\b|\btartan\b|\bgingham"), ("geometric", r"\bgeometric"),
            ("ethnic motifs", r"\bethnic motif|\bbandhani|\bbandhej|\bleh[ae]riya|\bikat\b|\bpaisley|\bblock[- ]print|\bbatik|\bkalamkari|\bajrakh"),
            ("abstract", r"\babstract"), ("animal print", r"\banimal print|\bleopard|\bzebra|\bsnake ?skin"),
            ("tie-dye", r"tie[- ]?(and[- ])?dye"), ("graphic", r"\bgraphic|\btypograph|\bslogan"),
            ("embroidered", r"\bembroider|\bchikankari|\bzari work|\bsequin"), ("colourblocked", r"colou?r[- ]?block"),
            ("self design", r"self[- ]design|\bjacquard|\bwoven design"), ("printed", r"\bprint(ed|s)?\b"),
            ("solid", r"\bsolid\b|\bplain\b")]
_SLEEVE = [("sleeveless", r"sleeveless|strappy|spaghetti|shoulder straps|strapless"),
           ("3/4 sleeves", r"three[- ]quarter|3/4"),
           ("long sleeves", r"\blong[, ]+(regular |puff |bishop |cuffed |flared |bell |roll-up )?sleeves?\b|full[- ]sleeves?"),
           ("short sleeves", r"\bshort[, ]+(regular |puff |flared |cap |extended |raglan )?sleeves?\b|half[- ]sleeves?|cap sleeves?|puff sleeves?")]
_NECK = [("v-neck", r"\bv[- ]neck"), ("mandarin collar", r"mandarin|band collar|chinese collar"),
         ("round neck", r"round neck|crew neck"), ("boat neck", r"boat neck"), ("square neck", r"square neck"),
         ("sweetheart neck", r"sweetheart"), ("off-shoulder", r"off[- ]the[- ]shoulder|off[- ]shoulder"),
         ("halter neck", r"\bhalter"), ("high neck", r"high neck|turtle ?neck|mock neck"),
         ("collar", r"shirt collar|spread collar|button[- ]down collar|polo collar|\bcollar\b")]
# sleeves and necklines only mean something for these
_UPPER = {"top", "t-shirt", "shirt", "kurta", "kurta set", "dress", "jumpsuit", "sweater", "sweatshirt", "jacket", "blazer",
          "anarkali set", "salwar suit", "co-ord set", "nehru jacket", "sharara set"}


def _first(rules, *texts):
    for text in texts:
        for value, rx in rules:
            if re.search(rx, text):
                return value
    return ""


def style_attributes(ptype, title, description=""):
    """{fit, pattern, sleeve, neck} for one listing; "" where the listing doesn't say."""
    t, d = title.lower(), description.lower()[:400]
    fit = "relaxed" if ptype in ("palazzo", "sharara set") else _first(_FIT, t, d)
    upper = ptype in _UPPER
    return dict(fit=fit, pattern=_first(_PATTERN, t, d),
                sleeve=_first(_SLEEVE, t, d) if upper else "",
                neck=_first(_NECK, t, d) if upper else "")
