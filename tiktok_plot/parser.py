"""Parse a TikTok plot file into structured scenes.

Format
------
An optional YAML-ish front matter block, then one scene per line::

    ---
    title: Why your coffee tastes bad
    style: claude
    seconds_per_scene: 3
    ---
    POV: you spent $300 on a grinder | shots/grinder.jpg
    (4s) Your water is the problem | shots/tap.png | slow push-in from the left
    Nobody tells you this | a pour-over kettle, steam rising

Rules:

* Every non-empty line that is not a comment is exactly one scene.
* ``|`` splits the line into fields. The first field is always the on-screen
  text. Each later field is either the *picture the author supplied* (a URL, a
  ``data:`` URI, or a path to an image file) or a *visual direction* in prose.
  They can appear in either order, and either may be omitted.
* ``(3s)`` / ``(2.5s)`` at the start of a line overrides that scene's duration.
* ``#`` starts a comment line. Text may still contain ``#`` (hashtags) as long
  as the line does not *begin* with one.
* ``img:`` in front of a field forces it to be read as a picture, for filenames
  the extension check would otherwise miss.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

FRONT_MATTER_FENCE = "---"
DURATION_RE = re.compile(r"^\(\s*(\d+(?:\.\d+)?)\s*s\s*\)\s*", re.IGNORECASE)
TRUTHY = {"true", "yes", "y", "1", "on"}
FALSY = {"false", "no", "n", "0", "off"}

DEFAULT_SECONDS_PER_SCENE = 3.0
MIN_SCENE_SECONDS = 0.5
MAX_SCENE_SECONDS = 30.0

IMAGE_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif",
    ".bmp", ".tif", ".tiff", ".heic", ".heif",
}
IMAGE_PREFIX = "img:"
REMOTE_SCHEMES = ("http://", "https://")


class ParseError(ValueError):
    """Raised when a plot file cannot be understood."""


@dataclass
class Scene:
    """One line of the plot: a single picture with text on it."""

    index: int
    text: str
    visual: str
    seconds: float
    line_number: int
    role: str = "beat"
    image: str = ""
    image_kind: str = ""

    @property
    def has_image(self) -> bool:
        """True when the author supplied the picture for this scene."""
        return bool(self.image)

    @property
    def image_is_local(self) -> bool:
        """True when the picture is a file on disk that still needs hosting."""
        return self.image_kind == "local"

    def resolved_image(self, base_dir: Path | None = None) -> Path | None:
        """Absolute path of a local picture, or ``None`` for remote/no picture."""
        if not self.image_is_local:
            return None
        candidate = Path(self.image).expanduser()
        if not candidate.is_absolute() and base_dir is not None:
            candidate = Path(base_dir) / candidate
        return candidate

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Plot:
    """A parsed plot: metadata plus an ordered list of scenes."""

    scenes: list[Scene]
    title: str = ""
    style: str = ""
    aspect: str = "9:16"
    seconds_per_scene: float = DEFAULT_SECONDS_PER_SCENE
    voiceover: bool = False
    music: str = ""
    notes: str = ""
    extras: dict[str, str] = field(default_factory=dict)
    base_dir: Path | None = None

    @property
    def duration(self) -> float:
        return round(sum(scene.seconds for scene in self.scenes), 2)

    @property
    def with_images(self) -> list[Scene]:
        """Scenes whose picture the author supplied."""
        return [scene for scene in self.scenes if scene.has_image]

    @property
    def local_images(self) -> list[Scene]:
        """Scenes whose picture is a local file, so still needs a public URL."""
        return [scene for scene in self.scenes if scene.image_is_local]

    def missing_images(self, base_dir: Path | None = None) -> list[Scene]:
        """Scenes pointing at a local picture that is not on disk."""
        base = base_dir if base_dir is not None else self.base_dir
        missing = []
        for scene in self.local_images:
            resolved = scene.resolved_image(base)
            if resolved is None or not resolved.is_file():
                missing.append(scene)
        return missing

    def apply_asset_base(self, asset_base: str) -> None:
        """Rewrite every local picture to ``<asset_base>/<path>``.

        This is the hand-off after uploading the pictures somewhere public:
        HyperFrames has to be able to fetch each one over HTTPS.
        """
        prefix = asset_base.rstrip("/")
        for scene in self.scenes:
            if scene.image_is_local:
                scene.image = f"{prefix}/{scene.image.lstrip('./').lstrip('/')}"
                scene.image_kind = "url"

    def apply_asset_map(self, mapping: dict[str, str]) -> None:
        """Rewrite specific local pictures to the public URLs given."""
        for scene in self.scenes:
            if scene.image in mapping:
                scene.image = mapping[scene.image]
                scene.image_kind = "data" if scene.image.startswith("data:") else "url"

    @property
    def hook(self) -> Scene | None:
        return self.scenes[0] if self.scenes else None

    @property
    def payoff(self) -> Scene | None:
        return self.scenes[-1] if self.scenes else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "style": self.style,
            "aspect": self.aspect,
            "seconds_per_scene": self.seconds_per_scene,
            "voiceover": self.voiceover,
            "music": self.music,
            "notes": self.notes,
            "extras": self.extras,
            "duration": self.duration,
            "scene_count": len(self.scenes),
            "supplied_images": len(self.with_images),
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _split_front_matter(lines: list[str]) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Return (front_matter_lines, body_lines) as (line_number, text) pairs."""
    numbered = list(enumerate(lines, start=1))
    # Leading blanks and comments may sit above the fence, so skip past them
    # rather than treating the front matter as scene lines.
    first = next(
        (
            i
            for i, (_, raw) in enumerate(numbered)
            if raw.strip() and not raw.strip().startswith("#")
        ),
        None,
    )
    if first is None or numbered[first][1].strip() != FRONT_MATTER_FENCE:
        return [], numbered

    for i in range(first + 1, len(numbered)):
        if numbered[i][1].strip() == FRONT_MATTER_FENCE:
            return numbered[first + 1 : i], numbered[i + 1 :]
    raise ParseError(
        f"front matter opened on line {numbered[first][0]} but never closed "
        f"with a matching '{FRONT_MATTER_FENCE}'"
    )


def _coerce_bool(key: str, value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in TRUTHY:
        return True
    if lowered in FALSY:
        return False
    raise ParseError(f"'{key}' must be true or false, got {value!r}")


def _coerce_seconds(key: str, value: str) -> float:
    try:
        seconds = float(value.strip().rstrip("sS"))
    except ValueError:
        raise ParseError(f"'{key}' must be a number of seconds, got {value!r}") from None
    if not MIN_SCENE_SECONDS <= seconds <= MAX_SCENE_SECONDS:
        raise ParseError(
            f"'{key}' must be between {MIN_SCENE_SECONDS} and {MAX_SCENE_SECONDS} seconds, "
            f"got {seconds}"
        )
    return seconds


def _parse_front_matter(entries: list[tuple[int, str]]) -> dict[str, Any]:
    meta: dict[str, Any] = {"extras": {}}
    for line_number, raw in entries:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ParseError(f"line {line_number}: front matter needs 'key: value', got {line!r}")
        key, _, value = line.partition(":")
        key = key.strip().lower().replace("-", "_")
        value = value.strip()
        if key in {"title", "style", "aspect", "music", "notes"}:
            meta[key] = value
        elif key == "voiceover":
            meta[key] = _coerce_bool(key, value)
        elif key == "seconds_per_scene":
            meta[key] = _coerce_seconds(key, value)
        else:
            meta["extras"][key] = value
    return meta


def classify_field(field_text: str) -> tuple[str, str]:
    """Classify one ``|``-separated field.

    Returns ``(kind, value)`` where kind is ``"url"``, ``"data"`` or ``"local"``
    for a supplied picture, and ``"visual"`` for a prose direction.
    """
    value = field_text.strip()
    if not value:
        return "visual", ""

    forced = value.lower().startswith(IMAGE_PREFIX)
    if forced:
        value = value[len(IMAGE_PREFIX) :].strip()

    lowered = value.lower()
    if lowered.startswith(REMOTE_SCHEMES):
        return "url", value
    if lowered.startswith("data:image/"):
        return "data", value
    # A bare path is a picture when it looks like an image file. Prose that
    # merely mentions a filename does not, since the check is on the tail.
    if Path(value).suffix.lower() in IMAGE_SUFFIXES:
        return "local", value
    if forced:
        return "local", value
    return "visual", value


def _parse_scene_line(line_number: int, raw: str, default_seconds: float, index: int) -> Scene:
    line = raw.strip()
    seconds = default_seconds
    match = DURATION_RE.match(line)
    if match:
        seconds = _coerce_seconds("scene duration", match.group(1))
        line = line[match.end() :].strip()

    fields = line.split("|")
    text = fields[0].strip()

    image = ""
    image_kind = ""
    directions: list[str] = []
    for field_text in fields[1:]:
        kind, value = classify_field(field_text)
        if not value:
            continue
        if kind == "visual":
            directions.append(value)
        elif image:
            raise ParseError(
                f"line {line_number}: two pictures on one scene ({image!r} and {value!r}) "
                "— split it into two lines"
            )
        else:
            image, image_kind = value, kind

    visual = ", ".join(directions)
    if not text and not visual and not image:
        raise ParseError(f"line {line_number}: scene has no text, no picture and no visual")
    return Scene(
        index=index,
        text=text,
        visual=visual,
        seconds=seconds,
        line_number=line_number,
        image=image,
        image_kind=image_kind,
    )


def parse_plot(source: str) -> Plot:
    """Parse plot text into a :class:`Plot`."""
    front_matter, body = _split_front_matter(source.splitlines())
    meta = _parse_front_matter(front_matter)
    default_seconds = meta.get("seconds_per_scene", DEFAULT_SECONDS_PER_SCENE)

    scenes: list[Scene] = []
    for line_number, raw in body:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        scenes.append(_parse_scene_line(line_number, raw, default_seconds, len(scenes) + 1))

    if not scenes:
        raise ParseError("plot has no scenes — add at least one line of on-screen text")

    # The first line is the scroll-stopper and the last one is the payoff; both
    # get different treatment downstream, so label them here.
    scenes[0].role = "hook"
    scenes[-1].role = "payoff" if len(scenes) > 1 else "hook"

    extras = meta.pop("extras", {})
    return Plot(scenes=scenes, extras=extras, **meta)


def parse_plot_file(path: str | Path) -> Plot:
    """Parse a plot file from disk."""
    source_path = Path(path)
    text = source_path.read_text(encoding="utf-8")
    plot = parse_plot(text)
    plot.base_dir = source_path.parent
    if not plot.title:
        plot.title = source_path.stem.replace("-", " ").replace("_", " ").strip().title()
    return plot
