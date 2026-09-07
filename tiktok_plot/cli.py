"""Command line interface: plot file in, HyperFrames brief out."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parser import ParseError, Plot, parse_plot, parse_plot_file
from .prompt import build_prompt
from .storyboard import build_storyboard

DESCRIPTION = """\
Turn a plain-text TikTok plot (one line = one picture with text) into a
HyperFrames video brief, a scene JSON, and an HTML storyboard.
"""


def _load(path: str) -> Plot:
    if path == "-":
        return parse_plot(sys.stdin.read())
    return parse_plot_file(path)


def _write(destination: str | None, content: str, label: str) -> None:
    if destination is None or destination == "-":
        sys.stdout.write(content)
        return
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"{label}: {target}", file=sys.stderr)


def _cmd_prompt(args: argparse.Namespace) -> int:
    _write(args.out, build_prompt(_load(args.plot)), "prompt")
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    _write(args.out, _load(args.plot).to_json() + "\n", "scenes")
    return 0


def _cmd_storyboard(args: argparse.Namespace) -> int:
    _write(args.out, build_storyboard(_load(args.plot)), "storyboard")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    plot = _load(args.plot)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "prompt.md").write_text(build_prompt(plot), encoding="utf-8")
    (out / "scenes.json").write_text(plot.to_json() + "\n", encoding="utf-8")
    (out / "storyboard.html").write_text(build_storyboard(plot), encoding="utf-8")
    print(
        f"{len(plot.scenes)} scenes · {plot.duration:g}s\n"
        f"  {out / 'prompt.md'}\n"
        f"  {out / 'scenes.json'}\n"
        f"  {out / 'storyboard.html'}",
        file=sys.stderr,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tiktok-plot", description=DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str, handler, default_out: str | None = None):
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        sub.add_argument("plot", help="path to the plot file, or - for stdin")
        sub.add_argument(
            "-o",
            "--out",
            default=default_out,
            help="write here instead of stdout",
        )
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
        print(f"tiktok-plot: no such plot file: {exc.filename}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
