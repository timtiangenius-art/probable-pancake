# tiktok-plot

Give it a plot where **each line is one picture with text on it**. It gives you a
HyperFrames brief, a scene list, and a storyboard you can look at before spending
a render.

```
plot.txt  ──►  prompt.md      ──►  HyperFrames compose  ──►  MP4
               scenes.json
               storyboard.html
```

## The plot format

The only rule that matters: **one non-empty line = one scene**.

```
---
title: Why your coffee tastes bad
style: warm film-grain kitchen photography, shallow depth of field
seconds_per_scene: 3
music: mellow lo-fi beat, no lyrics
---
(2s) You spent $300 on a grinder | close-up of a burr grinder on marble, morning light
And it still tastes like a gas station | a sad paper cup on a car dashboard
Your tap water is 98% of the cup | tap water filling a clear glass
(4s) Same beans. Different planet. | two identical cups side by side, steam curling
```

| Syntax | Meaning |
| --- | --- |
| `text \| visual` | Left of the pipe is the text burned on screen, right is what the picture shows. |
| `text` | Text only — the picture is inferred from it. |
| `\| visual` | Picture only, no text. |
| `(2.5s) text` | Override this one scene's duration. |
| `# note` | Comment line, skipped. A `#` *inside* a line is kept, so hashtags are fine. |

Front matter is optional. Recognised keys: `title`, `style`, `aspect` (`9:16`
default, plus `1:1`, `16:9`, `4:5`), `seconds_per_scene`, `voiceover`, `music`,
`notes`. Anything else you put there is passed through to the brief as extra
direction.

## Use it

```bash
python3 -m tiktok_plot.cli build examples/coffee.txt -o build/coffee
# build/coffee/prompt.md  build/coffee/scenes.json  build/coffee/storyboard.html
```

Or one piece at a time — each subcommand prints to stdout, or to `-o FILE`, and
reads `-` for stdin:

```bash
python3 -m tiktok_plot.cli prompt      plot.txt        # the HyperFrames brief
python3 -m tiktok_plot.cli parse       plot.txt        # scenes as JSON
python3 -m tiktok_plot.cli storyboard  plot.txt -o s.html
pbpaste | python3 -m tiktok_plot.cli prompt -
```

Installing it puts the same thing on your PATH as `tiktok-plot`:

```bash
pip install -e .
tiktok-plot build plot.txt -o build/mine
```

## Making the video

`prompt.md` is the whole input to HyperFrames. In Claude Code, the bundled
`/tiktok-video` skill does it end to end: paste your plot, and it saves it,
builds the brief, calls HyperFrames `compose`, waits for the render, and hands
back the video. Outside of that, paste `prompt.md` into HyperFrames yourself.

The brief pins down the things a video agent otherwise guesses: canvas size,
scene order, per-scene duration, and the exact on-screen copy (marked verbatim,
so your lines don't get "improved"). It also reserves the bottom 15% and right
12% of frame, where TikTok's own UI sits.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Layout

| Path | What it is |
| --- | --- |
| `tiktok_plot/parser.py` | Plot text → `Plot`/`Scene` objects |
| `tiktok_plot/prompt.py` | `Plot` → HyperFrames brief |
| `tiktok_plot/storyboard.py` | `Plot` → standalone HTML preview |
| `tiktok_plot/cli.py` | `prompt` / `parse` / `storyboard` / `build` |
| `.claude/skills/tiktok-video/` | The `/tiktok-video` Claude Code skill |
| `examples/coffee.txt` | A worked example |
