#!/usr/bin/env python3
"""WCAG contrast check of the theme tokens in frontend/src/styles/index.css (light + dark).
Measures token pairs only; it does NOT replace looking at the rendered pages."""
import re, sys
css = open("frontend/src/styles/index.css").read()

def block(sel):
    out = {}
    for body in re.findall(r"(?m)^" + sel + r"\s*\{([^}]*)\}", css):          # every :root / .dark block (tokens + course colours)
        out.update({k: (int(a), int(b), int(c)) for k, a, b, c in re.findall(r"--([\w-]+):\s*(\d+)\s+(\d+)\s+(\d+)", body)})
    return out

def lum(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4
    r, g, b = map(f, c); return 0.2126 * r + 0.7152 * g + 0.0722 * b

def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la + 0.05) / (lb + 0.05)

light, dark = block(":root"), block(r"\.dark")
fail = 0
for name, t in (("light", light), ("dark", dark)):
    rows = [("body text (ink) on page", t["ink"], t["base"], 4.5), ("headings (navy) on page", t["navy"], t["base"], 4.5),
            ("navy on card surface", t["navy"], t["surface"], 4.5), ("muted text on page", t["muted"], t["base"], 4.5),
            ("accent on page", t["accent"], t["base"], 3.0), ("ok on page", t["ok"], t["base"], 3.0), ("bad on page", t["bad"], t["base"], 3.0)]
    for i in range(12):
        rows.append((f"course colour c{i} vs navy text", t["navy"], t[f"c{i}"], 4.5))
    # semantic tones (pills, alerts, buttons) are bg/fg PAIRS; also success/danger text on page and card
    for tone in ("ok", "warn", "bad", "info", "lav"):
        rows.append((f"tone-{tone}: text on its background", t[f"{tone}-fg"], t[f"{tone}-bg"], 4.5))
    rows += [("success text on page", t["ok-fg"], t["base"], 4.5), ("danger text on page", t["bad-fg"], t["base"], 4.5),
             ("warning text on page", t["warn-fg"], t["base"], 4.5), ("accent (links) on page", t["accent"], t["base"], 4.5),
             ("muted on card surface", t["muted"], t["surface"], 4.5), ("success text on card", t["ok-fg"], t["surface"], 4.5)]
    rows += [("brand name 'Campus' (blue end) on page, large text", t["brand-a"], t["base"], 3.0), ("brand name 'Campus' (violet end) on page, large text", t["brand-b"], t["base"], 3.0),
             ("brand name 'Opti' (navy) on page", t["navy"], t["base"], 4.5)]
    splash = tuple(round(t["lav-bg"][k] * .72 + t["base"][k] * .28) for k in range(3))        # splash glass over the page
    rows += [("splash: 'Campus' blue end on glass", t["brand-a"], splash, 3.0), ("splash: 'Campus' violet end on glass", t["brand-b"], splash, 3.0), ("splash: 'Opti' navy on glass", t["navy"], splash, 4.5)]
    for nm in ("lavender", "peri", "sky", "peach", "rose", "mint"):      # translucent chips that use navy text (bg-X/60 over surface)
        bg = tuple(round(t[nm][k] * .6 + t["surface"][k] * .4) for k in range(3))
        rows.append((f"chip bg-{nm}/60 with navy text", t["navy"], bg, 4.5))
    print(f"--- {name} theme")
    for label, fg, bg, need in rows:
        r = ratio(fg, bg); ok = r >= need; fail += not ok
        if not ok or "c" in label[:7] and label.startswith("course") and not ok:
            print(f"  FAIL {label}: {r:.2f} (< {need})")
    worst = min(ratio(t["navy"], t[f"c{i}"]) for i in range(12))
    print(f"  checked {len(rows)} pairs; lowest course-colour contrast {worst:.2f}")
print("RESULT:", "all pairs pass" if not fail else f"{fail} pair(s) below target")
sys.exit(1 if fail else 0)
