#!/usr/bin/env python3
"""Build the SVG assets used by README.md, in light and dark variants.

    python3 build.py

IBM Plex (SIL OFL) is downloaded once into .fonts/ and embedded as a subset,
so the images look the same wherever GitHub renders them.
"""
import base64
import io
import math
import pathlib
import urllib.request
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FONT_DIR = ROOT / ".fonts"
FONT_URL = "https://cdn.jsdelivr.net/fontsource/fonts/{}@latest/latin-{}-normal.woff2"

THEMES = {
    "dark": dict(bg="#070b11", bg2="#0b121b", border="#1d2735", dot="#1a2534", link="#24324a",
                 node="#3d4e66", text="#e8eef6", muted="#97a7bb", label="#7c8ea5", accent="#3ddcc2",
                 pill="#0c131c", pill_border="#2a3850"),
    "light": dict(bg="#f7f9fb", bg2="#eef2f6", border="#d9e0e8", dot="#dbe2ea", link="#c3cdd9",
                  node="#8796a8", text="#0b1220", muted="#46566a", label="#56677b", accent="#0b7a6a",
                  pill="#ffffff", pill_border="#d0d8e2"),
}

# Lucide icons (ISC licence), 24px grid
ICONS = {
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/>'
                '<rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
}


class Font:
    def __init__(self, family, weight):
        self.name = f"{family}-{weight}"
        self.path = FONT_DIR / f"{self.name}.woff2"
        if not self.path.exists():
            FONT_DIR.mkdir(exist_ok=True)
            self.path.write_bytes(urllib.request.urlopen(FONT_URL.format(family, weight)).read())
        tt = TTFont(self.path)
        self.cmap, self.hmtx, self.upm = tt.getBestCmap(), tt["hmtx"], tt["head"].unitsPerEm

    def width(self, text, size):
        return sum(self.hmtx[self.cmap[ord(c)]][0] for c in text) * size / self.upm

    def embed(self, chars):
        tt = TTFont(self.path)
        sub = subset.Subsetter()
        sub.populate(text="".join(sorted(chars)))
        sub.subset(tt)
        tt.flavor = "woff2"
        buf = io.BytesIO()
        tt.save(buf)
        return base64.b64encode(buf.getvalue()).decode()


SANS = {w: Font("ibm-plex-sans", w) for w in (400, 500, 600)}
MONO = Font("ibm-plex-mono", 400)


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts, self.css, self.used = [], [], {}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, font, size, fill, anchor="start", attrs=""):
        self.used.setdefault(font, set()).update(s)
        self.add(f'<text x="{x:g}" y="{y:g}" font-family="\'{font.name}\', system-ui, sans-serif" '
                 f'font-size="{size}" fill="{fill}" text-anchor="{anchor}"{attrs}>{escape(s)}</text>')

    def save(self, name):
        faces = "".join(f"@font-face{{font-family:'{f.name}';src:url(data:font/woff2;base64,{f.embed(c)}) format('woff2')}}"
                        for f, c in self.used.items())
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}" role="img"><title>{escape(self.title)}</title>'
               f'<style>{faces}{"".join(self.css)}</style>{"".join(self.parts)}</svg>')
        ASSETS.mkdir(exist_ok=True)
        (ASSETS / name).write_text(svg)


def contrast(a, b):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# --- banner: a network map where a scan travels from the internet and each host locks in turn

W, H = 1280, 440
LOOP = 8.0      # seconds per cycle
SPEED = 210.0   # px per second
START = 0.5     # seconds before the scan leaves the internet node
HOLD_END, RESET_END = 86, 93  # % of the loop: secured state holds, then fades back

NODES = {  # name: (x, y, label x, label y, label anchor)
    "internet": (728, 220, 728, 256, "middle"),
    "fw-edge": (842, 220, 842, 272, "middle"),
    "web-dmz": (962, 100, 962, 72, "middle"),
    "core-sw": (962, 220, 948, 204, "end"),
    "vpn-ipsec": (962, 340, 962, 376, "middle"),
    "siem": (1085, 110, 1085, 82, "middle"),
    "ad-dc01": (1085, 220, 1085, 256, "middle"),
    "backup": (1085, 330, 1085, 366, "middle"),
    "db-core": (1200, 220, 1200, 270, "middle"),
}
LINKS = [("internet", "fw-edge"), ("fw-edge", "web-dmz"), ("fw-edge", "core-sw"), ("fw-edge", "vpn-ipsec"),
         ("vpn-ipsec", "core-sw"), ("core-sw", "siem"), ("core-sw", "ad-dc01"), ("core-sw", "backup"),
         ("ad-dc01", "db-core"), ("backup", "db-core")]
# scan routes: (node path, node the route branches from)
ROUTES = [(["internet", "fw-edge", "core-sw", "ad-dc01", "db-core"], None),
          (["fw-edge", "web-dmz"], "fw-edge"), (["fw-edge", "vpn-ipsec"], "fw-edge"),
          (["core-sw", "siem"], "core-sw"), (["core-sw", "backup"], "core-sw")]
LOCK_R = 19


def dist(a, b):
    (ax, ay), (bx, by) = NODES[a][:2], NODES[b][:2]
    return math.hypot(bx - ax, by - ay)


def schedule():
    """Arrival time of the scan at each node, and timing of each route's pulse."""
    arrive, pulses = {"internet": START}, []
    for path, _ in ROUTES:
        t0 = arrive[path[0]]
        legs = [dist(a, b) for a, b in zip(path, path[1:])]
        for i, node in enumerate(path[1:]):
            arrive[node] = t0 + sum(legs[:i + 1]) / SPEED
        pulses.append((path, t0, sum(legs)))
    return arrive, pulses


def pct(t):
    return round(t / LOOP * 100, 2)


def banner(theme):
    t = THEMES[theme]
    svg = Svg(W, H, "Leonard Lumati Opasanjo, cybersecurity specialist")
    arrive, pulses = schedule()
    ease = "cubic-bezier(.16,1,.3,1)"
    css = svg.css
    css.append(f".n{{fill:{t['accent']};stroke:{t['accent']};animation:{LOOP}s {ease} infinite both}}"
               f".lit{{stroke:{t['accent']};stroke-opacity:.55;animation:{LOOP}s {ease} infinite both}}"
               f".ring{{fill:none;stroke:{t['accent']};stroke-width:1.5;opacity:0;transform-box:fill-box;"
               f"transform-origin:center;animation:{LOOP}s cubic-bezier(.2,.8,.3,1) infinite both}}"
               f".pulse{{fill:none;stroke:{t['accent']};stroke-width:3.5;stroke-linecap:round;"
               f"animation:{LOOP}s linear infinite both}}"
               "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")

    # background card, dot grid faded in toward the map side
    svg.add(f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg"]}"/>'
            f'<stop offset="1" stop-color="{t["bg2"]}"/></linearGradient>'
            f'<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
            f'<circle cx="12" cy="12" r="1.2" fill="{t["dot"]}"/></pattern>'
            f'<linearGradient id="fade" x1="0" x2="1"><stop offset=".45" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".7" stop-color="#fff"/></linearGradient>'
            f'<mask id="m"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>'
            f'<clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath></defs>'
            f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="url(#bg)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#dots)" mask="url(#m)"/></g>'
            f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="17.5" fill="none" stroke="{t["border"]}"/>')

    # identity
    name_font, name_size = SANS[600], 72
    for line in ("Leonard Lumati", "Opasanjo"):
        assert name_font.width(line, name_size) < 640, line
    svg.text(72, 156, "Leonard Lumati", name_font, name_size, t["text"], attrs=' letter-spacing="-1.4"')
    svg.text(72, 234, "Opasanjo", name_font, name_size, t["text"], attrs=' letter-spacing="-1.4"')
    svg.text(72, 294, "Cybersecurity specialist", SANS[500], 30, t["accent"])
    meta = "Mombasa, Kenya   ·   CCNA   ·   ISO/IEC 27701 Lead Auditor"
    assert SANS[400].width(meta, 20) < 640
    svg.text(72, 338, meta, SANS[400], 20, t["muted"], attrs=' xml:space="preserve"')

    # links: base line, then an accent overlay that stays lit once the scan has passed
    route_links = {(p[i], p[i + 1]) for p, _ in ROUTES for i in range(len(p) - 1)}
    for a, b in LINKS:
        (ax, ay), (bx, by) = NODES[a][:2], NODES[b][:2]
        line = f'x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}"'
        dash = ' stroke-dasharray="4 5"' if a == "internet" else ""
        svg.add(f'<line {line} stroke="{t["link"]}" stroke-width="1.75"{dash}/>')
        if (a, b) in route_links:
            k = f"l_{a}_{b}".replace("-", "")
            p = pct(arrive[b])
            css.append(f"@keyframes {k}{{0%,{p}%{{stroke-opacity:0}}{p + 2}%,{HOLD_END}%{{stroke-opacity:.55}}"
                       f"{RESET_END}%,100%{{stroke-opacity:0}}}}")
            svg.add(f'<line {line} class="lit" stroke-width="1.75"{dash} style="animation-name:{k}"/>')

    # scan pulses: a short lit segment travelling each route
    seg = 34
    for i, (path, t0, length) in enumerate(pulses):
        k = f"p{i}"
        pts = " ".join(f"{NODES[n][0]},{NODES[n][1]}" for n in path)
        css.append(f"@keyframes {k}{{0%,{pct(t0)}%{{stroke-dashoffset:{seg}}}"
                   f"{pct(t0 + (length + seg) / SPEED)}%,100%{{stroke-dashoffset:{-length:.1f}}}}}")
        svg.add(f'<polyline points="{pts}" class="pulse" stroke-dasharray="{seg} {length + seg:.1f}" '
                f'stroke-dashoffset="{-length:.1f}" style="animation-name:{k}"/>')

    # nodes
    for name, (x, y, lx, ly, anchor) in NODES.items():
        if name == "internet":
            svg.add(f'<circle cx="{x}" cy="{y}" r="10" fill="{t["bg"]}" stroke="{t["node"]}" stroke-width="1.75" stroke-dasharray="3 3"/>')
        else:
            k, p = f"n_{name}".replace("-", ""), pct(arrive[name])
            r = LOCK_R if name == "db-core" else 8
            idle_fill = t["bg"]
            on_fill = t["accent"] + "26" if name == "db-core" else t["accent"]
            css.append(f"@keyframes {k}{{0%,{p}%{{fill:{idle_fill};stroke:{t['node']}}}"
                       f"{p + 2}%,{HOLD_END}%{{fill:{on_fill};stroke:{t['accent']}}}"
                       f"{RESET_END}%,100%{{fill:{idle_fill};stroke:{t['node']}}}}}"
                       f"@keyframes r_{k}{{0%,{p}%{{opacity:0;transform:scale(1)}}{p + .4}%{{opacity:.8}}"
                       f"{p + 10}%,100%{{opacity:0;transform:scale({2.2 if name == 'db-core' else 3.2})}}}}")
            svg.add(f'<circle cx="{x}" cy="{y}" r="{r}" class="ring" style="animation-name:r_{k}"/>')
            svg.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{t["bg"]}"/>')
            svg.add(f'<circle cx="{x}" cy="{y}" r="{r}" class="n" stroke-width="2" '
                    f'style="fill:{on_fill};animation-name:{k}"/>')
            if name == "db-core":
                css.append(f"@keyframes i_{k}{{0%,{p}%{{stroke:{t['node']}}}{p + 2}%,{HOLD_END}%{{stroke:{t['accent']}}}"
                           f"{RESET_END}%,100%{{stroke:{t['node']}}}}}"
                           f"@keyframes h_{k}{{0%,{p}%{{opacity:0}}{p + 3}%,{HOLD_END}%{{opacity:1}}{RESET_END}%,100%{{opacity:0}}}}")
                svg.add(f'<g transform="translate({x - 9.6} {y - 9.6}) scale(.8)" fill="none" stroke="{t["accent"]}" '
                        f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" '
                        f'style="animation:i_{k} {LOOP}s {ease} infinite both">{ICONS["lock"]}</g>')
                svg.add(f'<g style="animation:h_{k} {LOOP}s {ease} infinite both">')
                svg.text(x, y - 32, "hardened", MONO, 15, t["accent"], "middle")
                svg.add("</g>")
        svg.text(lx, ly, name, MONO, 15, t["label"], anchor)
    svg.save(f"banner-{theme}.svg")


def pill(key, icon, label, theme):
    t, font, size, h = THEMES[theme], SANS[500], 16, 40
    w = round(16 + 18 + 10 + font.width(label, size) + 18)
    svg = Svg(w, h, label)
    svg.add(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="9" fill="{t["pill"]}" stroke="{t["pill_border"]}"/>'
            f'<g transform="translate(16 11) scale(.75)" fill="none" stroke="{t["accent"]}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>')
    svg.text(44, 25.5, label, font, size, t["text"])
    svg.save(f"{key}-{theme}.svg")


if __name__ == "__main__":
    for theme, t in THEMES.items():
        for fg in ("text", "muted", "label", "accent"):
            ratio = contrast(t[fg], t["bg"])
            assert ratio >= 4.5, f"{theme} {fg} contrast {ratio:.2f}"
        banner(theme)
        pill("linkedin", "linkedin", "LinkedIn", theme)
        pill("email", "mail", "Email", theme)
        pill("website", "globe", "opassecure.com", theme)
    print("built:", ", ".join(sorted(p.name for p in ASSETS.glob("*.svg"))))
