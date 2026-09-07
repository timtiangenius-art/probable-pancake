"""Command line interface: plot file in, HyperFrames brief out."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .hosting import HostingError, resolve_asset_base
from .parser import ParseError, Plot, parse_plot, parse_plot_file
from .prompt import build_prompt
from .storyboard import build_storyboard

DESCRIPTION = """\
Turn a plain-text TikTok plot (one line = one picture with text) into a
HyperFrames video brief, a scene JSON, and an HTML storyboard.
"""


def _load(args: argparse.Namespace) -> Plot:
    """Read the plot, then resolve supplied pictures to public URLs."""
    path = args.plot
    plot = parse_plot(sys.stdin.read()) if path == "-" else parse_plot_file(path)

    asset_map = getattr(args, "asset_map", None)
    if asset_map:
        mapping = json.loads(Path(asset_map).read_text(encoding="utf-8"))
        if not isinstance(mapping, dict):
            raise ParseError(f"{asset_map}: expected a JSON object of path -> URL")
        plot.apply_asset_map(mapping)

    asset_base = getattr(args, "asset_base", None)
    if asset_base:
        _report_missing(plot)
        plot_dir = plot.base_dir or Path.cwd()
        resolved = resolve_asset_base(asset_base, plot_dir)
        if resolved != asset_base:
            print(f"tiktok-plot: hosting pictures at {resolved}", file=sys.stderr)
        plot.apply_asset_base(resolved)
    return plot


def _report_missing(plot: Plot) -> None:
    """Warn about local pictures that are not where the plot says they are."""
    missing = plot.missing_images()
    for scene in missing:
        print(
            f"tiktok-plot: line {scene.line_number}: picture not found: {scene.image}",
            file=sys.stderr,
        )
    return None


def _warn_unhosted(plot: Plot) -> None:
    """Local pictures cannot be fetched by HyperFrames — say so before a render."""
    _report_missing(plot)
    local = plot.local_images
    if not local:
        return
    print(
        f"tiktok-plot: {len(local)} picture(s) are local files. HyperFrames can only "
        "fetch public URLs — upload them and re-run with --asset-base URL (or "
        "--asset-map FILE) before composing.",
        file=sys.stderr,
    )


def _write(destination: str | None, content: str, label: str) -> None:
    if destination is None or destination == "-":
        sys.stdout.write(content)
        return
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"{label}: {target}", file=sys.stderr)


def _cmd_prompt(args: argparse.Namespace) -> int:
    plot = _load(args)
    _warn_unhosted(plot)
    _write(args.out, build_prompt(plot), "prompt")
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    _write(args.out, _load(args).to_json() + "\n", "scenes")
    return 0


def _cmd_storyboard(args: argparse.Namespace) -> int:
    plot = _load(args)
    _report_missing(plot)
    _write(args.out, build_storyboard(plot), "storyboard")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    plot = _load(args)
    _warn_unhosted(plot)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "prompt.md").write_text(build_prompt(plot), encoding="utf-8")
    (out / "scenes.json").write_text(plot.to_json() + "\n", encoding="utf-8")
    (out / "storyboard.html").write_text(build_storyboard(plot), encoding="utf-8")
    supplied = len(plot.with_images)
    print(
        f"{len(plot.scenes)} scenes · {plot.duration:g}s · {supplied} supplied picture(s)\n"
        f"  {out / 'prompt.md'}\n"
        f"  {out / 'scenes.json'}\n"
        f"  {out / 'storyboard.html'}",
        file=sys.stderr,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tiktok-plot", description=DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_asset_flags(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--asset-base",
            help="public URL prefix for local pictures, e.g. https://cdn.example.com/shots. "
            "Pass 'github' to derive it from this repo's origin and branch.",
        )
        sub.add_argument(
            "--asset-map",
            help="JSON file mapping each local picture path to its public URL",
        )

    def add(name: str, help_text: str, handler, default_out: str | None = None):
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        sub.add_argument("plot", help="path to the plot file, or - for stdin")
        sub.add_argument(
            "-o",
            "--out",
            default=default_out,
            help="write here instead of stdout",
        )
        add_asset_flags(sub)
        sub.set_defaults(handler=handler)
        return sub

    add("prompt", "print the HyperFrames compose prompt", _cmd_prompt)
    add("parse", "print the parsed scenes as JSON", _cmd_parse)
    add("storyboard", "print a standalone HTML storyboard", _cmd_storyboard)

    build = subparsers.add_parser(
        "build",
        help="write prompt.md, scenes.json and storyboard.html to a directory",
        description="Write prompt.md, scenes.json and storyboard.html to a directory.",
    )
    build.add_argument("plot", help="path to the plot file, or - for stdin")
    build.add_argument("-o", "--out", default="build", help="output directory (default: build)")
    add_asset_flags(build)
    build.set_defaults(handler=_cmd_build)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except ParseError as exc:
        print(f"tiktok-plot: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"tiktok-plot: no such file: {exc.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"tiktok-plot: asset map is not valid JSON: {exc}", file=sys.stderr)
        return 2
    except HostingError as exc:
        print(f"tiktok-plot: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
