"""Render a parsed plot as a self-contained HTML storyboard.

This is the cheap check before spending a cloud render: it shows every scene as
a phone-shaped card with the exact on-screen text, its duration, and the visual
direction that will be sent to HyperFrames.
"""

from __future__ import annotations

import base64
import mimetypes
from html import escape
from pathlib import Path

from .parser import Plot, Scene

# Pictures are inlined so the storyboard is one portable file. Anything bigger
# than this is referenced by path instead of bloating the document.
MAX_INLINE_BYTES = 4 * 1024 * 1024

ASPECT_RATIO = {"9:16": "9 / 16", "1:1": "1 / 1", "16:9": "16 / 9", "4:5": "4 / 5"}

_CSS = """
:root {
  color-scheme: light dark;
  --bg: #0d0d0f;
  --panel: #17171c;
  --line: #2a2a33;
  --ink: #f4f4f6;
  --muted: #9a9aa8;
  --accent: #ff2d55;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 40px 24px 64px;
  background: var(--bg);
  color: var(--ink);
  font: 15px/1.5 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
}
header { max-width: 1100px; margin: 0 auto 32px; }
h1 { margin: 0 0 6px; font-size: 30px; letter-spacing: -0.02em; }
.meta { color: var(--muted); font-size: 14px; }
.meta strong { color: var(--ink); font-weight: 600; }
.grid {
  max-width: 1100px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 22px;
}
.card { display: flex; flex-direction: column; gap: 10px; }
.frame {
  position: relative;
  aspect-ratio: var(--ratio, 9 / 16);
  border: 1px solid var(--line);
  border-radius: 14px;
  background:
    radial-gradient(120% 80% at 50% 0%, #33333f 0%, #17171c 60%, #101014 100%);
  padding: 18px 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.frame::after {
  content: "";
  position: absolute;
  inset: auto 12% 15% 6%;
  border: 1px dashed rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  height: 0;
}
.caption {
  font-weight: 800;
  font-size: 17px;
  line-height: 1.25;
  text-align: center;
  text-wrap: balance;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.85);
  max-height: 100%;
  overflow: hidden;
}
.caption.empty { color: var(--muted); font-weight: 500; font-style: italic; }
.badge {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 11px;
  color: var(--muted);
}
.badge.role-hook, .badge.role-payoff { color: var(--accent); border-color: var(--accent); }
.secs { position: absolute; top: 10px; right: 10px; font-size: 11px; color: var(--muted); }
.visual { color: var(--muted); font-size: 13px; }
.visual em { color: #c9c9d4; font-style: normal; }
.photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.frame.has-photo .caption { position: relative; z-index: 1; }
.frame.has-photo::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.15) 45%, rgba(0,0,0,0.55) 100%);
}
.frame.has-photo .badge, .frame.has-photo .secs { z-index: 1; }
.warn { color: #ffb020; }
"""


def _image_src(scene: Scene, base_dir: Path | None) -> tuple[str, str]:
    """Return ``(src, note)`` for a scene's picture.

    Local files become ``data:`` URIs so the storyboard travels as one file;
    remote URLs are used directly. ``src`` is empty when there is no usable
    picture, and ``note`` explains why.
    """
    if not scene.has_image:
        return "", ""
    if not scene.image_is_local:
        return scene.image, ""

    path = scene.resolved_image(base_dir)
    if path is None or not path.is_file():
        return "", f"missing file: {scene.image}"
    if path.stat().st_size > MAX_INLINE_BYTES:
        return "", f"too large to inline: {scene.image}"

    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}", ""


def _card(
    index: int,
    role: str,
    seconds: float,
    text: str,
    visual: str,
    src: str = "",
    note: str = "",
) -> str:
    caption = (
        f'<div class="caption">{escape(text)}</div>'
        if text
        else '<div class="caption empty">image only</div>'
    )
    if visual:
        visual_html = f"<em>{escape(visual)}</em>"
    elif src or note:
        visual_html = "your picture"
    else:
        visual_html = "auto — inferred from the text"
    if note:
        visual_html += f' <span class="warn">{escape(note)}</span>'

    photo = f'<img class="photo" src="{escape(src, quote=True)}" alt="">' if src else ""
    return f"""      <figure class="card">
        <div class="frame{' has-photo' if src else ''}">
          {photo}
          <span class="badge role-{escape(role)}">{index} · {escape(role)}</span>
          <span class="secs">{seconds:g}s</span>
          {caption}
        </div>
        <figcaption class="visual">{visual_html}</figcaption>
      </figure>"""


def build_storyboard(plot: Plot, base_dir: Path | None = None) -> str:
    """Return a standalone HTML document previewing every scene.

    Local pictures are read relative to ``base_dir`` (defaulting to the plot
    file's own directory) and inlined, so the result is one portable file.
    """
    base = base_dir if base_dir is not None else plot.base_dir
    ratio = ASPECT_RATIO.get(plot.aspect.strip(), ASPECT_RATIO["9:16"])
    title = plot.title or "Untitled TikTok"
    bits = [
        f"<strong>{len(plot.scenes)}</strong> scenes",
        f"<strong>{plot.duration:g}s</strong> total",
        f"<strong>{escape(plot.aspect)}</strong>",
    ]
    if plot.style:
        bits.append(f"style <strong>{escape(plot.style)}</strong>")
    bits.append("voiceover <strong>%s</strong>" % ("on" if plot.voiceover else "off"))
    if plot.with_images:
        bits.append(f"<strong>{len(plot.with_images)}</strong> supplied pictures")

    cards = []
    for scene in plot.scenes:
        src, note = _image_src(scene, base)
        cards.append(
            _card(scene.index, scene.role, scene.seconds, scene.text, scene.visual, src, note)
        )
    cards = "\n".join(cards)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storyboard · {escape(title)}</title>
<style>{_CSS}
.frame {{ --ratio: {ratio}; }}
</style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p class="meta">{" · ".join(bits)}</p>
  </header>
  <main class="grid">
{cards}
  </main>
</body>
</html>
"""
