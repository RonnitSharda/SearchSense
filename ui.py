"""Presentation layer for SearchSense: theme CSS and HTML fragments (no business logic)."""
import html

CSS = """
<style>
:root{--ink:#282C3F;--mute:#7E818C;--line:#EAEAEC;--bg:#F5F5F6;--pink:#FF3F6C;--pinkL:#FFF0F3;--navy:#1A1F5C;
--green:#14958F;--greenL:#E6F5F4;--amber:#F59E0B;--amberL:#FFF6E0;--red:#D93A3A;--redL:#FDECEC;}
html,body,[class*="css"]{font-family:"Inter","Segoe UI",system-ui,sans-serif;}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:2.2rem;max-width:1280px}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line)}

/* top bar */
.ss-top{display:flex;align-items:center;justify-content:space-between;padding:4px 2px 14px}
.ss-logo{font-weight:800;font-size:26px;letter-spacing:-.8px;color:var(--ink)}
.ss-logo b{color:var(--pink)}
.ss-tag{font-size:13px;color:var(--mute)}
.ss-badge{font-size:11px;font-weight:700;letter-spacing:.6px;color:var(--pink);background:var(--pinkL);border-radius:20px;padding:4px 10px}

/* search input */
div[data-testid="stForm"]{border:0;padding:0}
div[data-testid="stTextInput"] input{height:52px;border-radius:12px;border:1.5px solid var(--line);background:var(--bg);font-size:16px;padding:0 18px}
div[data-testid="stTextInput"] input:focus{border-color:var(--pink);background:#fff;box-shadow:0 0 0 3px #FF3F6C22}
div[data-testid="stFormSubmitButton"] button,.stButton button[kind="primary"]{height:52px;border-radius:12px;font-weight:700;background:var(--pink);border:0;color:#fff}
div[data-testid="stFormSubmitButton"] button:hover,.stButton button[kind="primary"]:hover{background:#E8335E;color:#fff}

/* scenario pills */
.try{font-size:12px;font-weight:700;letter-spacing:.8px;color:var(--mute);margin:10px 0 4px}
.stButton button[kind="secondary"]{border-radius:20px;border:1px solid var(--line);background:#fff;color:var(--ink);font-size:13px;padding:2px 4px!important;min-height:34px!important;width:100%}
.stButton button[kind="secondary"] p,.stButton button[kind="secondary"] .stMarkdownEllipsis{font-size:13px;overflow:visible!important;text-overflow:clip!important}
.stButton button[kind="secondary"]:hover{border-color:var(--pink);color:var(--pink)}

/* router + AI understanding */
.router{display:flex;flex-wrap:wrap;align-items:center;gap:8px;font-size:12.5px;color:var(--mute);padding:8px 0}
.pill{display:inline-block;border-radius:20px;padding:3px 11px;font-size:12px;font-weight:700}
.p-navy{background:var(--navy);color:#fff}.p-pink{background:var(--pink);color:#fff}.p-amber{background:var(--amber);color:#3a2a00}
.p-green{background:var(--green);color:#fff}.p-grey{background:#94969F;color:#fff}.p-red{background:var(--red);color:#fff}
.aim{background:#FFF8FA;border:1px solid #FFE3EA;border-left:3px solid var(--pink);border-radius:8px;padding:9px 14px;margin:2px 0 10px}
.aim .t{color:var(--pink);font-weight:700;font-size:11.5px}
.aim .i{color:var(--ink);font-size:14.5px;font-weight:500;margin-top:1px}
.map{font-size:12.5px;color:var(--mute);margin-top:2px}
.relax{background:var(--amberL);border:1px solid #F8D98A;border-radius:12px;padding:10px 14px;font-size:14px;margin:8px 0}
.layer{font-size:11px;font-weight:800;letter-spacing:1px;color:var(--mute);margin:14px 0 8px;text-transform:uppercase}
.rescount{font-size:15px;color:var(--ink);margin:6px 0 10px}.rescount b{font-weight:800}

/* product card (bordered streamlit container) */
CARD{border:1px solid var(--line)!important;border-radius:14px!important;background:#fff;overflow:hidden;transition:box-shadow .15s;height:100%}
CARD:hover{box-shadow:0 6px 22px #282C3F18}
.pimg{position:relative;aspect-ratio:3/3.3;display:flex;align-items:flex-end;justify-content:center;overflow:hidden;border-radius:10px;margin-bottom:8px}
.pimg img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.pimg svg{margin-bottom:10px}
.rate{position:absolute;left:8px;bottom:8px;background:#fffffff2;border-radius:6px;padding:2px 7px;font-size:12px;font-weight:700;color:var(--ink)}
.rate i{color:#14958F;font-style:normal}
.idx{position:absolute;left:8px;top:8px;background:var(--ink);color:#fff;border-radius:6px;padding:1px 8px;font-size:12px;font-weight:700}
.pbrand{font-weight:800;font-size:14px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pname{font-size:13.5px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:3px}
.price{font-weight:800;color:var(--ink);font-size:15px}
.price s{font-weight:400;color:var(--mute);font-size:12.5px;margin-left:6px}
.price em{font-style:normal;color:#E5833A;font-size:12.5px;font-weight:700;margin-left:6px}
.why{font-size:12.5px;color:#4A4E63;line-height:1.35;margin:5px 0;min-height:34px}
.foot{min-height:96px}
.badge{display:inline-block;font-size:11.5px;font-weight:700;padding:3px 8px;border-radius:6px;margin:2px 0}
.b-high{background:var(--greenL);color:#0E706B}.b-medium{background:var(--amberL);color:#8A5A00}.b-low{background:var(--redL);color:var(--red)}
.note{font-size:11.5px;background:var(--amberL);color:#8A5A00;border-radius:6px;padding:3px 8px;display:inline-block;margin-top:4px}
.chk{font-size:11px;color:var(--mute);margin-top:4px}

/* editable chips */
span[data-baseweb="tag"],span[data-tag]{background:var(--pinkL)!important;color:var(--ink)!important;border-radius:16px!important}
span[data-baseweb="tag"] *,span[data-tag] *{color:var(--ink)!important}
span[data-tag] svg{stroke:var(--pink)}

/* buttons inside product cards */
CARD .stButton button{height:36px!important;min-height:36px!important;border-radius:8px!important;font-size:13px;font-weight:700}
CARD .stButton button[kind="primary"]{background:var(--pink);color:#fff;border:0}

/* home hero */
.hero{background:linear-gradient(100deg,#FFF0F3 0%,#FFF8F0 60%,#F4F1FF 100%);border-radius:14px;padding:18px 22px;margin:4px 0 12px}
.hero-t{font-size:22px;font-weight:800;color:var(--ink);letter-spacing:-.4px}
.hero-s{font-size:13.5px;color:#4A4E63;margin-top:3px;max-width:820px}
.why.sub{color:var(--mute);min-height:0}

/* test cases */
.tc-intro{font-size:14px;color:#4A4E63;background:var(--bg);border-radius:10px;padding:10px 14px;margin:4px 0 14px}
.tc-head{display:flex;gap:12px;align-items:center;margin-bottom:8px}
.tc-ic{font-size:26px;width:46px;height:46px;border-radius:12px;background:var(--pinkL);display:flex;align-items:center;justify-content:center}
.tc-name{font-weight:800;font-size:16px;color:var(--ink)}
.tc-tag{display:inline-block;font-size:11px;font-weight:700;color:var(--pink);background:var(--pinkL);border-radius:20px;padding:2px 9px;margin-top:2px}
.tc-q{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;background:var(--bg);border-radius:8px;padding:8px 10px;color:var(--ink);margin:6px 0 8px;min-height:58px}
.tc-l{font-size:10.5px;font-weight:800;letter-spacing:.8px;color:var(--mute);text-transform:uppercase;margin-top:6px}
.tc-t{font-size:13px;color:#4A4E63;line-height:1.4;min-height:36px}
.trace-q{font-size:18px;font-weight:700;color:var(--ink);margin:4px 0 0}

/* top results */
BEST{border:2px solid var(--pink)!important;box-shadow:0 6px 24px #FF3F6C26}
TOP{border:1.5px solid #FFB3C6!important}
.ribbon{position:absolute;right:8px;top:8px;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:800;letter-spacing:.4px}
.ribbon.best{background:var(--pink);color:#fff}.ribbon.top{background:#fff;color:var(--pink);border:1px solid #FFB3C6}

/* suggested searches */
.sugg{font-size:12px;font-weight:700;color:var(--mute);letter-spacing:.4px;margin:2px 0 4px}
.friendly{font-size:14px;color:var(--ink);margin:4px 0 2px}.friendly b{color:var(--pink)}

/* customer-support hand-off */
.helpbox{background:#F0F7FF;border:1px solid #CFE3FF;border-left:4px solid #3B82F6;border-radius:10px;padding:14px 18px;margin:6px 0 12px}
.hb-t{font-size:17px;font-weight:800;color:var(--ink)}.hb-s{font-size:14px;color:#4A4E63;margin-top:4px}

/* reasoning bubble: you typed -> I understood -> so I'm showing */
.bubble{display:flex;gap:12px;background:#fff;border:1px solid #FFD6E0;border-radius:4px 16px 16px 16px;padding:12px 16px;margin:4px 0 10px;
        box-shadow:0 2px 10px #FF3F6C14}
.b-ic{flex:0 0 30px;height:30px;border-radius:50%;background:var(--pink);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800}
.b-body{flex:1}
.b-row{display:flex;gap:10px;padding:3px 0;font-size:14px;line-height:1.45}
.b-k{flex:0 0 112px;font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--mute);padding-top:2px}
.b-v{color:var(--ink)}.b-v b{color:var(--ink)}
.b-why{font-size:12.5px;color:var(--mute);margin-top:2px}

/* agent loop strip */
.steps-h{font-size:11px;font-weight:800;letter-spacing:.8px;color:var(--mute);text-transform:uppercase;margin:2px 0 6px}
.steps{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:12px}
.st{flex:1 1 0;min-width:112px;border-radius:10px;padding:8px 10px;background:#fff;border:1px solid var(--line);position:relative}
.st:not(:last-child)::after{content:"›";position:absolute;right:-8px;top:40%;font-size:16px;font-weight:800;color:#C4C5CA;z-index:1}
.st-n{position:absolute;right:8px;top:6px;font-size:11px;font-weight:800;color:var(--mute)}
.st-t{font-size:12.5px;font-weight:800;color:var(--ink);padding-right:14px}
.st-d{font-size:11.5px;color:#4A4E63;line-height:1.35;margin-top:2px}
.st-done{border-top:3px solid var(--pink)}
.st-skip{border-top:3px solid #D4D5D9;background:#FAFAFB}.st-skip .st-t,.st-skip .st-d{color:#94969F}
.st-relax{border-top:3px solid var(--amber);background:var(--amberL)}
.st-ask{border-top:3px solid #3B82F6;background:#F0F7FF}
.ask{background:#F0F7FF;border:1px solid #CFE3FF;border-radius:10px;padding:10px 14px;margin:2px 0 8px;font-size:14.5px}

/* refine (follow-up) bar under the bubble */
.refine-l{font-weight:800;color:var(--pink);font-size:14px;white-space:nowrap}
.refine-q{font-size:12px;font-weight:700;color:var(--mute);text-align:right;padding-right:4px}

/* product Q&A */
.qa{background:var(--bg);border-radius:10px;padding:8px 12px;margin:6px 0}
.qa-q{font-size:13px;font-weight:700;color:var(--ink)}.qa-a{font-size:13.5px;color:var(--ink);margin-top:2px}
.qa-s{font-size:11px;color:var(--mute);margin-top:2px}

/* trace + risks */
.step{border-left:3px solid var(--pink);padding:4px 12px;margin:8px 0;font-size:13.5px}
.step b{color:var(--ink)}
.tool{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:var(--bg);border-radius:6px;padding:2px 6px}
.risk-high{border-left:5px solid var(--red);background:var(--redL);padding:10px 14px;border-radius:8px;margin:8px 0}
.risk-medium{border-left:5px solid var(--amber);background:var(--amberL);padding:10px 14px;border-radius:8px;margin:8px 0}
.risk-info{border-left:5px solid #94969F;background:var(--bg);padding:10px 14px;border-radius:8px;margin:8px 0;font-size:14px}
.empty{text-align:center;padding:48px 10px;color:var(--mute)}
.empty h3{color:var(--ink);margin-bottom:6px}
</style>"""

# A bordered st.container is a stVerticalBlock in current Streamlit and a stVerticalBlockBorderWrapper in older releases.
_CARD = (':is(div[data-testid="stVerticalBlock"]:has(> .element-container .pc),'
         'div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > .element-container .pc))')
_card = lambda marker: (f':is(div[data-testid="stVerticalBlock"]:has(> .element-container {marker}),'
                        f'div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > .element-container {marker}))')
CSS = CSS.replace("BEST", _card(".pc.best")).replace("TOP", _card(".pc.top")).replace("CARD", _CARD)


SILH = {
    "garment": '<svg width="64" height="104" viewBox="0 0 46 72"><path d="M15 4h16l5 10-5 6 13 48H2L15 20l-5-6z" fill="#fff" opacity=".85"/></svg>',
    "shirt": '<svg width="92" height="92" viewBox="0 0 60 60"><path d="M20 6l10 6 10-6 14 10-6 10-6-4v32H18V22l-6 4-6-10z" fill="#fff" opacity=".85"/></svg>',
    "jeans": '<svg width="70" height="104" viewBox="0 0 40 64"><path d="M6 2h28l2 60H24l-4-40-4 40H4z" fill="#fff" opacity=".85"/></svg>',
    "lamp": '<svg width="80" height="104" viewBox="0 0 50 64"><path d="M10 26 Q25 2 40 26z" fill="#fff" opacity=".9"/><rect x="23" y="26" width="4" height="28" fill="#fff" opacity=".9"/><rect x="14" y="54" width="22" height="5" rx="2" fill="#fff" opacity=".9"/></svg>',
    "bottle": '<svg width="60" height="104" viewBox="0 0 36 64"><rect x="12" y="2" width="12" height="10" rx="2" fill="#fff" opacity=".9"/><rect x="6" y="12" width="24" height="48" rx="6" fill="#fff" opacity=".9"/></svg>',
    "cushion": '<svg width="96" height="96" viewBox="0 0 60 60"><rect x="8" y="10" width="44" height="40" rx="10" fill="#fff" opacity=".85"/></svg>',
}


def silhouette_key(p):
    t = p["type"]
    if "shirt" in t or "jacket" in t: return "shirt"
    if "jeans" in t: return "jeans"
    if "lamp" in t: return "lamp"
    if p["category"] == "personal care": return "bottle"
    if "cushion" in t: return "cushion"
    return "garment"


def image_block(p, idx=None, tall=False, ribbon=None):
    """Product image: real photo if the item has one, else a tinted silhouette. The tinted silhouette always renders behind the photo, so a dead image URL shows the silhouette (no onerror: Streamlit's React renderer rejects it)."""
    sw = p["swatch"]
    img = f'<img src="{html.escape(p["image"])}" alt="" loading="lazy" referrerpolicy="no-referrer">' if p.get("image") else ""
    rate = f'<span class="rate">{p["rating"]} <i>★</i></span>' if p.get("rating") else ""
    num = f'<span class="idx">#{idx}</span>' if idx else ""
    if ribbon:
        num += f'<span class="ribbon {"best" if ribbon == "Best match" else "top"}">{html.escape(ribbon)}</span>'
    style = f"background:linear-gradient(160deg,{sw}55,{sw})" + (";aspect-ratio:3/3.8" if tall else "")
    return f'<div class="pimg" style="{style}">{SILH[silhouette_key(p)]}{img}{num}{rate}</div>'


def price_block(p):
    mrp = p.get("mrp")
    if mrp and mrp > p["price"]:
        off = round(100 * (mrp - p["price"]) / mrp)
        return f'<div class="price">₹{p["price"]:,}<s>₹{mrp:,}</s><em>{off}% off</em></div>'
    return f'<div class="price">₹{p["price"]:,}</div>'


# Dark theme. Streamlit paints its widgets from the light theme in config.toml, which CSS variables can't reach, so dark
# mode inverts the whole app's colours and inverts photos and product tiles back, keeping their real colours.
DARK_CSS = """
<style>
html,body{background:#101114}
.stApp{filter:invert(1) hue-rotate(180deg);background:#EFEFF2}
.pimg,[data-testid="stImage"],img{filter:invert(1) hue-rotate(180deg)}
.pimg img{filter:none}
[data-testid="stToast"]{filter:invert(1) hue-rotate(180deg)}
</style>"""
