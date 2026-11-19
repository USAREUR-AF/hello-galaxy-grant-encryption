#!/usr/bin/env python3
"""Draw the README figure from the scenario it shows.

    python3 -I docs/figures/make-figures.py           # write docs/figures/*.svg
    python3 -I docs/figures/make-figures.py --check   # exit 1 if a committed figure is out of date

Each figure is written twice, `<name>-light.svg` and `<name>-dark.svg`, for a
`<picture>` element. Every name and message in the figure is checked against the
scenario script it comes from, and the build stops if one is no longer there.
Standard library only; the output is deterministic.
"""

import os
import re
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

THEMES = {
    "light": {
        "paper": "#ffffff", "panel": "#f6f8fa", "ink": "#1f2328", "quiet": "#59636e", "rule": "#d1d9e0",
        "line": "#818b98", "accent": "#0969da", "accent_soft": "#ddf4ff", "on_accent": "#ffffff",
        "good": "#1a7f37", "good_bg": "#dafbe1", "crit": "#cf222e", "crit_bg": "#ffebe9",
        "warn": "#9a6700", "warn_bg": "#fff8c5", "mute": "#6e7781",
    },
    "dark": {
        "paper": "#0d1117", "panel": "#161b22", "ink": "#e6edf3", "quiet": "#9198a1", "rule": "#3d444d",
        "line": "#7d8590", "accent": "#4493f8", "accent_soft": "#132c4c", "on_accent": "#0d1117",
        "good": "#3fb950", "good_bg": "#12261e", "crit": "#f85149", "crit_bg": "#2f1517",
        "warn": "#d29922", "warn_bg": "#2e2510", "mute": "#8b949e",
    },
}
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
W = 880          # every figure's width; a README column shows it at about 830 px
KIND = {"plain": ("panel", "rule"), "accent": ("accent_soft", "accent"), "good": ("good_bg", "good"),
        "crit": ("crit_bg", "crit"), "warn": ("warn_bg", "warn")}


def n(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def tw(s, size, mono=False, bold=False):
    """Text width estimate; the browser lint confirms it."""
    if mono:
        return len(s) * size * 0.61
    w = 0.0
    for c in s:
        if c in "il.,:;|!'`·1 ":
            w += 0.30
        elif c in "ft()[]/-":
            w += 0.36
        elif c in "mwMW@%":
            w += 0.86
        elif c.isupper() or c in "0123456789≤≥²→":
            w += 0.64
        else:
            w += 0.55
    return w * size * (1.06 if bold else 1.0)


def wrap(s, width, size, mono=False, bold=False):
    out, line = [], ""
    for word in s.split(" "):
        t = word if not line else line + " " + word
        if tw(t, size, mono, bold) <= width or not line:
            line = t
        else:
            out.append(line)
            line = word
    if line:
        out.append(line)
    return out


class SVG:
    def __init__(self, w, h, title, desc):
        self.w, self.h, self.title, self.desc = w, h, title, desc
        self.items = []

    def add(self, s):
        self.items.append(s)

    def rect(self, x, y, w, h, fill="panel", stroke="rule", rx=8, sw=1, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="{%s}" stroke="{%s}" stroke-width="%s"%s/>'
                 % (n(x), n(y), n(w), n(h), n(rx), fill, stroke, n(sw), d))

    def text(self, x, y, s, size=14, fill="ink", anchor="start", bold=False, mono=False):
        self.add('<text x="%s" y="%s" font-size="%s" fill="{%s}" text-anchor="%s"%s%s>%s</text>'
                 % (n(x), n(y), n(size), fill, anchor, ' font-weight="600"' if bold else "",
                    ' font-family="%s"' % MONO if mono else "", escape(s)))

    def line(self, x1, y1, x2, y2, stroke="line", sw=1.5, dash=None, arrow=False):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        m = ' marker-end="url(#arrow-%s)"' % stroke if arrow else ""
        self.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="{%s}" stroke-width="%s"%s%s/>'
                 % (n(x1), n(y1), n(x2), n(y2), stroke, n(sw), d, m))

    def box(self, x, y, w, h, title, rows=(), kind="plain", dash=None, size=14, mono_rows=(), title_fill="ink"):
        """A box with a bold title and wrapped rows; rows whose index is in mono_rows are set in mono."""
        fill, stroke = KIND[kind]
        self.rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.5, dash=dash)
        self.text(x + 14, y + 26, title, 15, bold=True, fill=title_fill)
        yy = y + 50
        for i, r in enumerate(rows):
            mono = i in mono_rows
            fill_r = "ink"
            if isinstance(r, tuple):
                r, fill_r = r
            for ln in wrap(r, w - 28, size if not mono else 13, mono=mono):
                self.text(x + 14, yy, ln, size if not mono else 13, fill=fill_r, mono=mono)
                yy += 20
        return yy

    def render(self, theme):
        t = THEMES[theme]
        body = "\n".join(self.items)
        for k, v in t.items():
            body = body.replace("{%s}" % k, v)
        markers = "".join(
            '<marker id="arrow-%s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="%s"/></marker>' % (k, t[k])
            for k in ("line", "accent", "good", "crit"))
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
                'aria-labelledby="t d" font-family="%s">\n<title id="t">%s</title>\n<desc id="d">%s</desc>\n'
                '<defs>%s</defs>\n<rect width="100%%" height="100%%" rx="12" fill="%s"/>\n%s\n</svg>\n'
                % (self.w, self.h, self.w, self.h, SANS.replace("'", "&apos;"), escape(self.title),
                   escape(self.desc), markers, t["paper"], body))


def header(f, title, sub):
    f.text(24, 38, title, 20, bold=True)
    f.text(24, 62, sub, 14, fill="quiet")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def need(rel, *needles):
    """Fail the build if a fact the figure prints is no longer in the file it comes from."""
    text = read(rel)
    missing = [s for s in needles if s not in text]
    if missing:
        sys.exit("make-figures: %s no longer contains %s; update the figure" % (rel, ", ".join(map(repr, missing))))


def main(figures, argv):
    check = "--check" in argv
    stale = []
    for name, fn in figures:
        fig = fn()
        for theme in THEMES:
            p = os.path.join(HERE, "%s-%s.svg" % (name, theme))
            out = fig.render(theme)
            if check:
                if not os.path.isfile(p) or open(p, encoding="utf-8").read() != out:
                    stale.append(os.path.relpath(p, ROOT))
            else:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(out)
                print(os.path.relpath(p, ROOT))
    if stale:
        print("out of date: " + ", ".join(stale) + "; run python3 -I docs/figures/make-figures.py", file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------- the hero
SCEN = "scenarios/03-read-and-deny/run.py"


def fig_read_and_deny():
    need(SCEN, '"weather-feed"', '"acme-sensors"', '"northwind"', '"outsider/eve"',
         'b"STATION 7: wind 040 at 12 kt"', 'f"data/{producer.member_id}/obs"')
    title = "An outsider receives the same bytes and cannot open them"
    f = SVG(W, 466, title,
            "Scenario 03: the data owner grants the weather-feed stream to org northwind; the key service, off the "
            "data path, mints one data key, wraps it to each member and publishes the signed bundle; the producer "
            "unwraps its own slot and publishes ciphertext; the Zenoh fabric delivers the same bytes to every "
            "subscriber; the northwind consumer opens the message and outsider/eve, an enrolled identity outside "
            "the audience, is denied because it holds no slot.")
    header(f, title, "Scenario 03 as it runs: the read check is the encryption, not the router.")
    top, h = 88, 120
    f.box(24, top, 200, h, "Data owner", ["goat access grant:", "weather-feed", "to org northwind"])
    f.box(248, top, 300, h, "Key service", ["off the data path: derives the audience from the grant, mints one "
                                            "data key, wraps it to each member, then signs the key bundle"], kind="accent")
    f.box(572, top, 284, h, "Producer, acme-sensors", ["a member of its own audience: it unwraps its own slot, "
                                                        "then seals every message"])
    f.line(224, top + h / 2, 246, top + h / 2, arrow=True)
    by = 262
    f.rect(24, by, W - 48, 32, fill="panel", stroke="line", rx=6, sw=1.5)
    f.text(W / 2, by + 21, "Zenoh fabric: no broker, no decryptor; every subscriber receives the same bytes", 14,
           anchor="middle", fill="quiet")
    f.line(290, top + h, 290, by - 2, stroke="accent", sw=2, arrow=True)
    f.text(300, 238, "keys/weather-feed/prod/1", 13, mono=True, fill="accent")
    f.line(600, top + h, 600, by - 2, sw=2, arrow=True)
    f.text(610, 238, "data/weather-feed/prod/obs", 13, mono=True, fill="quiet")
    cy = 336
    f.line(227, by + 32, 227, cy - 2, stroke="good", sw=2, arrow=True)
    f.line(653, by + 32, 653, cy - 2, stroke="crit", sw=2, arrow=True)
    f.box(24, cy, 406, 88, "Member, northwind consumer",
          ["holds 1 key and unwraps its slot", ("opened gen 1: STATION 7: wind 040 at 12 kt", "good")],
          kind="good", mono_rows=(1,))
    f.box(450, cy, 406, 88, "Outsider, outsider/eve",
          ["enrolled on the fabric, not in the audience: 0 keys", ("denied on gen 1: no slot", "crit")],
          kind="crit", mono_rows=(1,))
    f.text(24, 452, "Run it yourself: ./bin/grant-enc 03", 14, fill="quiet")
    return f


if __name__ == "__main__":
    sys.exit(main([("read-and-deny", fig_read_and_deny)], sys.argv[1:]))
