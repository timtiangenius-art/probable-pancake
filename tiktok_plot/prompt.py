"""Turn a parsed :class:`~tiktok_plot.parser.Plot` into a HyperFrames brief.

The brief is a single natural-language prompt. It is what gets handed to the
HyperFrames ``compose`` tool, which does the actual layout, animation and
render — so the job here is to be unambiguous about the things a video agent
would otherwise guess: canvas, pacing, exact on-screen copy, and scene order.
"""

from __future__ import annotations

from .parser import Plot, Scene

ASPECT_CANVAS = {
    "9:16": "1080x1920 (vertical, 9:16)",
    "1:1": "1080x1080 (square, 1:1)",
    "16:9": "1920x1080 (landscape, 16:9)",
    "4:5": "1080x1350 (portrait, 4:5)",
}

ROLE_DIRECTION = {
    "hook": (
        "This is the scroll-stopper. Land the text within the first few frames, "
        "make it the largest type in the video, and start on the strongest image."
    ),
    "payoff": (
        "This is the payoff/CTA and the last thing on screen. Hold it a beat longer "
        "than the animation needs so the text is readable after the motion settles."
    ),
    "beat": "",
}


def _canvas(aspect: str) -> str:
    return ASPECT_CANVAS.get(aspect.strip(), ASPECT_CANVAS["9:16"])


def _visual_for(scene: Scene) -> str:
    if scene.visual:
        return scene.visual
    return (
        f"choose one clear image that literally illustrates “{scene.text}” "
        "— one subject, no collage, nothing that competes with the text"
    )


def _scene_block(scene: Scene) -> str:
    lines = [
        f"### Scene {scene.index} — {scene.seconds:g}s ({scene.role})",
        f"- On-screen text (use verbatim, do not reword): “{scene.text}”"
        if scene.text
        else "- On-screen text: none, image only",
        f"- Picture: {_visual_for(scene)}",
    ]
    direction = ROLE_DIRECTION.get(scene.role, "")
    if direction:
        lines.append(f"- Direction: {direction}")
    return "\n".join(lines)


def build_prompt(plot: Plot) -> str:
    """Build the HyperFrames compose prompt for ``plot``."""
    title = plot.title or "Untitled TikTok"
    parts: list[str] = []

    parts.append(
        f"Create a TikTok-style short video titled “{title}”.\n\n"
        f"Canvas: {_canvas(plot.aspect)}. "
        f"{len(plot.scenes)} scenes, {plot.duration:g}s total."
    )

    rules = [
        "One scene per beat below, in the exact order given — do not merge, split, "
        "reorder or invent scenes.",
        "Every scene is one still picture with its text burned on top, TikTok caption "
        "style: heavy sans-serif, high contrast against the image, centred in the upper "
        "or middle third, generous safe margins so nothing sits under the TikTok UI "
        "(keep the bottom ~15% and right ~12% clear).",
        "Use the on-screen text verbatim. Do not paraphrase, translate, expand or add "
        "extra copy, watermarks, logos or captions of your own.",
        "Hold each scene for the duration given; the text must be fully readable for at "
        "least three quarters of that time.",
        "Keep motion subtle and continuous — a slow push-in or drift on the picture, "
        "quick cuts or fast fades between scenes. No spinning, no bouncing text, no "
        "transition that hides the copy.",
        "Keep type treatment, colour and framing identical across all scenes so the "
        "video reads as one piece.",
    ]
    if plot.voiceover:
        rules.append(
            "Add a voiceover that reads each scene's on-screen text, timed to that scene."
        )
    else:
        rules.append("No voiceover and no spoken narration.")
    if plot.music:
        rules.append(f"Music/audio: {plot.music}.")
    if plot.style:
        rules.append(f"Visual style: {plot.style}.")
    if plot.notes:
        rules.append(f"Extra direction from the author: {plot.notes}.")
    for key, value in plot.extras.items():
        rules.append(f"{key.replace('_', ' ').capitalize()}: {value}.")

    parts.append("## Rules\n" + "\n".join(f"- {rule}" for rule in rules))
    parts.append(
        "## Scenes\n\n" + "\n\n".join(_scene_block(scene) for scene in plot.scenes)
    )
    return "\n\n".join(parts).strip() + "\n"
