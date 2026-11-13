"""Look and feel of the Streamlit app: red-and-black theme, logo, hero banner, cards and the muscle body map.

All pictures are drawn here as SVG, so the app needs no image files and no image licences.
"""
import html

import streamlit as st

RED = "#E11D2E"
RED_DARK = "#8F0F1B"
BLACK = "#0B0B0D"
PANEL = "#141418"
PANEL_2 = "#1C1C22"
BORDER = "#2A2A31"
TEXT = "#F4F4F5"
MUTED = "#A1A1AA"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp li {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
[data-testid="stIconMaterial"] {{ font-family: 'Material Symbols Rounded' !important; }}
h1, h2, h3, .gc-title {{ font-family: 'Oswald', 'Impact', 'Arial Narrow', sans-serif !important; letter-spacing: .02em; }}
[data-testid="stAppViewContainer"] {{
  background: radial-gradient(1200px 500px at 85% -10%, rgba(225,29,46,.14), transparent 60%), {BLACK};
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #111114 0%, #0B0B0D 100%); border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] hr {{ border-color: {BORDER}; }}
.block-container {{ padding-top: 2.2rem; max-width: 1200px; }}

/* buttons */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
  border-radius: 10px; font-weight: 600; letter-spacing: .01em; transition: all .15s ease;
}}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primary"] {{
  background: linear-gradient(135deg, {RED} 0%, #B3121F 100%); border: 0; box-shadow: 0 6px 18px rgba(225,29,46,.25);
}}
.stButton > button:hover {{ transform: translateY(-1px); border-color: {RED}; }}

/* inputs, tabs, expanders, tables */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {{ border-radius: 10px !important; }}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: .25rem; border-bottom: 1px solid {BORDER}; }}
[data-testid="stTabs"] [aria-selected="true"] {{ color: {RED} !important; }}
[data-testid="stExpander"] {{ border: 1px solid {BORDER}; border-radius: 12px; background: {PANEL}; }}
[data-testid="stForm"] {{ border: 1px solid {BORDER}; border-radius: 14px; background: {PANEL}; padding: 1.2rem 1.2rem .6rem; }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
[data-testid="stChatMessage"] {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; }}

/* our own blocks */
.gc-hero {{ position: relative; border-radius: 18px; overflow: hidden; border: 1px solid {BORDER};
  background: linear-gradient(135deg, #17171C 0%, #0B0B0D 60%); padding: 0; }}
.gc-page-head {{ display: flex; align-items: center; gap: 14px; margin: 0 0 1.2rem; padding-bottom: .9rem;
  border-bottom: 1px solid {BORDER}; }}
.gc-page-head .bar {{ width: 6px; height: 42px; border-radius: 4px; background: linear-gradient(180deg, {RED}, {RED_DARK}); }}
.gc-page-head h1 {{ font-size: 2rem; margin: 0; padding: 0; line-height: 1.1; text-transform: uppercase; }}
.gc-page-head p {{ margin: .15rem 0 0; color: {MUTED}; font-size: .95rem; }}
.gc-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: .2rem 0 1.2rem; }}
.gc-card {{ background: linear-gradient(160deg, {PANEL_2} 0%, {PANEL} 100%); border: 1px solid {BORDER}; border-radius: 14px;
  padding: 16px 18px; position: relative; overflow: hidden; }}
.gc-card::after {{ content: ""; position: absolute; right: -30px; top: -30px; width: 90px; height: 90px; border-radius: 50%;
  background: radial-gradient(circle, rgba(225,29,46,.22), transparent 70%); }}
.gc-card .label {{ color: {MUTED}; font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }}
.gc-card .value {{ font-family: 'Oswald', 'Impact', sans-serif; font-size: 2.1rem; font-weight: 600; color: {TEXT}; line-height: 1.15; margin-top: 4px; }}
.gc-card .value.red {{ color: {RED}; }}
.gc-card .sub {{ color: {MUTED}; font-size: .8rem; margin-top: 2px; }}
.gc-panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; padding: 16px 18px; }}
.gc-section {{ font-family: 'Oswald', 'Impact', sans-serif; text-transform: uppercase; letter-spacing: .06em; font-size: 1.05rem;
  color: {TEXT}; margin: 1.4rem 0 .6rem; display: flex; align-items: center; gap: 8px; }}
.gc-section::before {{ content: ""; width: 14px; height: 3px; background: {RED}; border-radius: 2px; }}
.gc-alert {{ border: 1px solid rgba(225,29,46,.45); background: rgba(225,29,46,.08); border-radius: 12px; padding: 12px 16px;
  color: {TEXT}; margin-bottom: 1rem; }}
.gc-alert b {{ color: {RED}; }}
.gc-chip {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .75rem; font-weight: 600;
  border: 1px solid {BORDER}; background: {PANEL_2}; color: {MUTED}; margin-right: 6px; }}
.gc-chip.red {{ border-color: rgba(225,29,46,.5); color: #FF6B76; background: rgba(225,29,46,.1); }}
.gc-user {{ display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid {BORDER}; border-radius: 12px;
  background: {PANEL}; margin: .4rem 0 .8rem; }}
.gc-avatar {{ width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; font-weight: 700;
  background: linear-gradient(135deg, {RED}, {RED_DARK}); color: white; font-family: 'Oswald', sans-serif; font-size: 1rem; }}
.gc-user .name {{ font-weight: 600; color: {TEXT}; line-height: 1.1; }}
.gc-user .role {{ color: {MUTED}; font-size: .75rem; }}
.gc-feature {{ display: flex; gap: 12px; align-items: flex-start; margin: 14px 0; }}
.gc-feature .ico {{ width: 34px; height: 34px; flex: none; border-radius: 10px; display: grid; place-items: center;
  background: rgba(225,29,46,.12); border: 1px solid rgba(225,29,46,.35); color: {RED}; font-weight: 700; }}
.gc-feature .t {{ font-weight: 600; color: {TEXT}; }}
.gc-feature .d {{ color: {MUTED}; font-size: .9rem; }}
.gc-legend {{ display: flex; align-items: center; gap: 8px; color: {MUTED}; font-size: .78rem; justify-content: center; }}
.gc-legend .grad {{ width: 120px; height: 8px; border-radius: 4px; background: linear-gradient(90deg, rgba(225,29,46,.18), {RED}); }}
.gc-muted {{ color: {MUTED}; font-size: .85rem; }}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def logo(size: int = 30) -> str:
    """A barbell mark in red with the app name."""
    return f"""
<div style="display:flex;align-items:center;gap:10px;margin:.2rem 0 .4rem;">
<svg width="{size * 1.6}" height="{size}" viewBox="0 0 48 30" role="img" aria-label="AI Gym Coach">
  <rect x="0" y="13" width="48" height="4" rx="2" fill="{MUTED}"/>
  <rect x="5" y="5" width="5" height="20" rx="1.5" fill="{RED}"/><rect x="11" y="8" width="4" height="14" rx="1.5" fill="{RED}"/>
  <rect x="38" y="5" width="5" height="20" rx="1.5" fill="{RED}"/><rect x="33" y="8" width="4" height="14" rx="1.5" fill="{RED}"/>
</svg>
<div style="line-height:1;">
  <div class="gc-title" style="font-size:{size * 0.62}px;font-weight:700;color:{TEXT};text-transform:uppercase;">AI Gym Coach</div>
  <div style="font-size:{size * 0.34}px;color:{MUTED};letter-spacing:.14em;text-transform:uppercase;">Train smarter</div>
</div></div>"""


def hero(title: str, subtitle: str, subtitle2: str = "") -> str:
    """A wide banner: a lifter at the bar over a red pulse line."""
    t, s, s2 = html.escape(title), html.escape(subtitle), html.escape(subtitle2)
    return f"""
<div class="gc-hero"><svg viewBox="0 0 900 300" width="100%" role="img" aria-label="{t}" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="hg" x1="0" x2="1"><stop offset="0" stop-color="{RED}" stop-opacity=".0"/><stop offset=".5" stop-color="{RED}"/><stop offset="1" stop-color="{RED}" stop-opacity=".0"/></linearGradient>
    <radialGradient id="glow" cx=".72" cy=".55" r=".5"><stop offset="0" stop-color="{RED}" stop-opacity=".35"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>
    <pattern id="stripes" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)"><rect width="2" height="14" fill="#ffffff" fill-opacity=".035"/></pattern>
  </defs>
  <rect width="900" height="300" fill="url(#stripes)"/>
  <rect width="900" height="300" fill="url(#glow)"/>
  <polyline points="0,232 420,232 452,232 470,190 492,268 514,150 536,248 556,232 900,232" fill="none" stroke="url(#hg)" stroke-width="3"/>
  <g transform="translate(715,62) scale(.88)" fill="#16161B" stroke="{RED}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round">
    <rect x="-150" y="30" width="300" height="8" rx="4" fill="{MUTED}" stroke="none"/>
    <rect x="-140" y="2" width="16" height="64" rx="3" fill="{RED}" stroke="none"/><rect x="-120" y="12" width="12" height="44" rx="3" fill="{RED}" stroke="none"/>
    <rect x="124" y="2" width="16" height="64" rx="3" fill="{RED}" stroke="none"/><rect x="108" y="12" width="12" height="44" rx="3" fill="{RED}" stroke="none"/>
    <circle cx="0" cy="-8" r="20"/>
    <path d="M-62 34 L-34 70 L-22 120 M62 34 L34 70 L22 120"/>
    <path d="M-30 64 Q0 52 30 64 L26 140 Q0 150 -26 140 Z"/>
    <path d="M-24 140 L-34 196 L-30 236 M24 140 L34 196 L30 236" stroke-width="10"/>
  </g>
  <text x="44" y="118" fill="{TEXT}" font-family="Oswald, Impact, sans-serif" font-size="46" font-weight="700" letter-spacing="1">{t}</text>
  <text x="46" y="156" fill="{MUTED}" font-family="Inter, Segoe UI, sans-serif" font-size="17">{s}</text>
  <text x="46" y="180" fill="{MUTED}" font-family="Inter, Segoe UI, sans-serif" font-size="17">{s2}</text>
  <rect x="46" y="198" width="64" height="4" rx="2" fill="{RED}"/>
</svg></div>"""


def page_header(title: str, subtitle: str = ""):
    st.markdown(f'<div class="gc-page-head"><div class="bar"></div><div><h1>{html.escape(title)}</h1>'
                f'<p>{html.escape(subtitle)}</p></div></div>', unsafe_allow_html=True)


def section(title: str):
    st.markdown(f'<div class="gc-section">{html.escape(title)}</div>', unsafe_allow_html=True)


def cards(items: list[tuple[str, str, str, bool]]):
    """KPI cards: (label, value, sub text, highlight in red)."""
    body = "".join(
        f'<div class="gc-card"><div class="label">{html.escape(label)}</div>'
        f'<div class="value{" red" if red else ""}">{html.escape(str(value))}</div>'
        f'<div class="sub">{html.escape(sub)}</div></div>' for label, value, sub, red in items)
    st.markdown(f'<div class="gc-cards">{body}</div>', unsafe_allow_html=True)


def alert(html_text: str):
    st.markdown(f'<div class="gc-alert">{html_text}</div>', unsafe_allow_html=True)


def user_badge(username: str, role: str, is_demo: bool):
    initials = html.escape(username[:2].upper())
    tag = "Demo account" if is_demo else ("Admin" if role == "admin" else "Member")
    st.markdown(f'<div class="gc-user"><div class="gc-avatar">{initials}</div><div>'
                f'<div class="name">{html.escape(username)}</div><div class="role">{tag}</div></div></div>',
                unsafe_allow_html=True)


def feature(icon: str, title: str, text: str) -> str:
    return (f'<div class="gc-feature"><div class="ico">{icon}</div><div><div class="t">{html.escape(title)}</div>'
            f'<div class="d">{html.escape(text)}</div></div></div>')


# ---------------- muscle body map ----------------
# Simplified front and back figures; each muscle group is a set of shapes coloured by its share of training volume.
FRONT = {
    "shoulders": ['<ellipse cx="62" cy="88" rx="17" ry="14"/>', '<ellipse cx="138" cy="88" rx="17" ry="14"/>'],
    "chest": ['<path d="M72 80 Q86 74 99 78 L99 112 Q84 118 72 108 Z"/>', '<path d="M128 80 Q114 74 101 78 L101 112 Q116 118 128 108 Z"/>'],
    "biceps": ['<ellipse cx="51" cy="126" rx="10" ry="23"/>', '<ellipse cx="149" cy="126" rx="10" ry="23"/>'],
    "forearms": ['<ellipse cx="45" cy="177" rx="8" ry="24"/>', '<ellipse cx="155" cy="177" rx="8" ry="24"/>'],
    "abdominals": ['<rect x="81" y="118" width="38" height="64" rx="10"/>'],
    "quadriceps": ['<ellipse cx="84" cy="248" rx="16" ry="43"/>', '<ellipse cx="116" cy="248" rx="16" ry="43"/>'],
    "calves": ['<ellipse cx="84" cy="334" rx="10" ry="28"/>', '<ellipse cx="116" cy="334" rx="10" ry="28"/>'],
}
BACK = {
    "traps": ['<path d="M84 64 L116 64 L132 84 L100 96 L68 84 Z"/>'],
    "shoulders": ['<ellipse cx="62" cy="88" rx="17" ry="14"/>', '<ellipse cx="138" cy="88" rx="17" ry="14"/>'],
    "triceps": ['<ellipse cx="51" cy="126" rx="10" ry="23"/>', '<ellipse cx="149" cy="126" rx="10" ry="23"/>'],
    "forearms": ['<ellipse cx="45" cy="177" rx="8" ry="24"/>', '<ellipse cx="155" cy="177" rx="8" ry="24"/>'],
    "lats": ['<path d="M70 98 L84 100 L86 156 L74 146 Z"/>', '<path d="M130 98 L116 100 L114 156 L126 146 Z"/>'],
    "middle back": ['<rect x="86" y="98" width="28" height="48" rx="6"/>'],
    "lower back": ['<rect x="87" y="150" width="26" height="30" rx="6"/>'],
    "glutes": ['<ellipse cx="87" cy="200" rx="15" ry="16"/>', '<ellipse cx="113" cy="200" rx="15" ry="16"/>'],
    "hamstrings": ['<ellipse cx="85" cy="258" rx="15" ry="38"/>', '<ellipse cx="115" cy="258" rx="15" ry="38"/>'],
    "calves_back": ['<ellipse cx="85" cy="334" rx="12" ry="29"/>', '<ellipse cx="115" cy="334" rx="12" ry="29"/>'],
}
SILHOUETTE = ('<circle cx="100" cy="36" r="19"/><rect x="92" y="54" width="16" height="12" rx="4"/>'
              '<path d="M64 74 Q100 62 136 74 L134 190 Q100 204 66 190 Z"/>'
              '<ellipse cx="45" cy="210" rx="7" ry="9"/><ellipse cx="155" cy="210" rx="7" ry="9"/>'
              '<path d="M68 188 L132 188 L134 300 L104 300 L100 210 L96 300 L66 300 Z"/>'
              '<ellipse cx="84" cy="372" rx="11" ry="6"/><ellipse cx="116" cy="372" rx="11" ry="6"/>')


def _figure(groups: dict, share: dict, days: dict, label: str, max_width: int = 230, tips: dict | None = None,
            caption: bool = True) -> str:
    top = max([v for v in share.values() if v] or [1])
    parts = []
    for muscle, shapes in groups.items():
        name = "calves" if muscle == "calves_back" else muscle
        if name not in share:          # drawn for the shape only (traps, forearms): not a group the app tracks
            parts.append(f'<g fill="#18181D" stroke="#2E2E36" stroke-width="1.2">{"".join(shapes)}</g>')
            continue
        v = share.get(name, 0) or 0
        if v > 0:
            opacity = 0.25 + 0.75 * v / top
            fill = f'fill="{RED}" fill-opacity="{opacity:.2f}" stroke="{RED}" stroke-opacity=".9"'
        else:
            fill = 'fill="#2A2A31" stroke="#3A3A43"'
        if tips is not None:
            tip = tips.get(name, name)
        else:
            d = days.get(name)
            when = "not trained in this period" if d is None else f"last trained {d} day{'s' if d != 1 else ''} ago"
            tip = f"{name}: {v:.1f}% of volume, {when}"
        parts.append(f'<g {fill} stroke-width="1.2"><title>{html.escape(tip)}</title>{"".join(shapes)}</g>')
    label_svg = (f'<text x="100" y="396" text-anchor="middle" fill="{MUTED}" font-size="12" letter-spacing="3" '
                 f'font-family="Oswald, Impact, sans-serif">{label.upper()}</text>') if caption else ""
    return (f'<svg viewBox="0 0 200 400" width="100%" style="max-width:{max_width}px" role="img" '
            f'aria-label="{label} muscle map"><g fill="#18181D" stroke="#2E2E36" stroke-width="1.2">{SILHOUETTE}</g>'
            f'{"".join(parts)}{label_svg}</svg>')


def body_map(share: dict, days: dict) -> str:
    """Front and back figures; the more training volume a muscle group got, the redder it is."""
    return (f'<div class="gc-panel"><div style="display:flex;justify-content:space-around;gap:8px;">'
            f'{_figure(FRONT, share, days, "Front")}{_figure(BACK, share, days, "Back")}</div>'
            f'<div class="gc-legend"><span>less</span><span class="grad"></span><span>more volume</span>'
            f'<span style="display:inline-block;width:12px;height:8px;border-radius:2px;background:#2A2A31;margin-left:10px;">'
            f'</span><span>not trained</span></div></div>')


# ---------------- exercise cards ----------------
DRAWN_MUSCLES = {"calves" if m == "calves_back" else m for m in [*FRONT, *BACK]}
# The day's focus, as people say it, mapped to the muscle names of free-exercise-db
FOCUS_GROUPS = {"chest": ["chest"], "back": ["lats", "middle back", "lower back", "traps"],
                "shoulders": ["shoulders"], "arms": ["biceps", "triceps", "forearms"],
                "legs": ["quadriceps", "hamstrings", "glutes", "calves", "adductors", "abductors"],
                "core": ["abdominals"]}


def _muscles(text: str) -> list[str]:
    return [m for m in (text or "").split("; ") if m]


def exercise_card(name: str, primary: str, secondary: str, equipment: str, level: str, category: str,
                  last_time: str, description: str | None = None) -> str:
    """One exercise: a small front and back map (main muscles bright red, helpers lighter) and its details."""
    main, helpers = _muscles(primary), _muscles(secondary)
    share = {m: (100 if m in main else 40 if m in helpers else 0) for m in DRAWN_MUSCLES}
    tips = {m: f"{m}: {'main muscle' if m in main else 'helper muscle' if m in helpers else 'not used'}"
            for m in DRAWN_MUSCLES}
    maps = (_figure(FRONT, share, {}, "Front", 64, tips, caption=False)
            + _figure(BACK, share, {}, "Back", 64, tips, caption=False))
    chips = ("".join(f'<span class="gc-chip red">{html.escape(m)}</span>' for m in main)
             + "".join(f'<span class="gc-chip">{html.escape(m)}</span>' for m in helpers))
    meta = " · ".join(html.escape(x) for x in [equipment, level, category] if x)
    return (f'<div class="gc-panel" style="display:flex;gap:14px;align-items:center;margin-bottom:12px;">'
            f'<div style="display:flex;gap:2px;flex:none;width:132px;">{maps}</div>'
            f'<div style="min-width:0;"><div style="font-weight:600;color:{TEXT};text-transform:capitalize;'
            f'margin-bottom:6px;">{html.escape(name)}</div><div style="margin-bottom:6px;">{chips}</div>'
            f'<div class="gc-muted" style="text-transform:capitalize;">{meta}</div>'
            f'<div class="gc-muted" style="margin-top:4px;">{html.escape(last_time)}</div>'
            + (f'<div class="gc-muted" style="margin-top:6px;font-size:.8rem;line-height:1.35;">'
               f'{html.escape(description[:220] + ("…" if len(description) > 220 else ""))}</div>' if description else "")
            + '</div></div>')
