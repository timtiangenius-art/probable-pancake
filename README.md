# tiktok-plot

Give it a plot where **each line is one picture with text on it** — your own
picture, or one described for the video agent to source. It gives you a
HyperFrames brief, a scene list, and a storyboard you can look at before spending
a render.

```
plot.txt   ──►  prompt.md      ──►  HyperFrames compose  ──►  MP4
your pics       scenes.json
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
(2s) You spent $300 on a grinder | photos/grinder.jpg
And it still tastes like a gas station | photos/sad-cup.jpg | slow drift right
Your tap water is 98% of the cup | tap water filling a clear glass
(4s) Same beans. Different planet. | https://cdn.example.com/two-cups.jpg
```

Everything after the first `|` is either **your picture** or a **description**,
and the app tells them apart on its own: a URL, a `data:` URI, or a path ending
in an image extension is a picture; anything else is prose direction. Order does
not matter, and you can give both.

| Syntax | Meaning |
| --- | --- |
| `text \| photos/01.jpg` | Your picture, used as-is. |
| `text \| https://…/01.jpg` | Same, already hosted. |
| `text \| a kettle on a stove` | No picture — the video agent sources one from this. |
| `text \| photos/01.jpg \| slow push-in` | Your picture, plus how to move on it. |
| `text` | Text only; the picture is inferred from the text. |
| `\| photos/01.jpg` | Picture only, no text. |
| `(2.5s) text` | Override this one scene's duration. |
| `img:IMG_2049` | Force a field to be read as a picture when it has no extension. |
| `# note` | Comment line, skipped. A `#` *inside* a line is kept, so hashtags are fine. |

Picture paths are relative to the plot file. If one is missing, you are told
which line before anything gets rendered.

Front matter is optional. Recognised keys: `title`, `style`, `aspect` (`9:16`
default, plus `1:1`, `16:9`, `4:5`), `seconds_per_scene`, `voiceover`, `music`,
`notes`. Anything else you put there is passed through to the brief as extra
direction.

## Your pictures need a public URL

HyperFrames renders in the cloud, so it can only fetch pictures over HTTPS — a
file on your disk is invisible to it. `--asset-base` bridges that. If your plot
lives in a **public GitHub repo**, the repo is the host and one word does it:

```bash
git add photos/ && git commit -m "Add photos" && git push
python3 -m tiktok_plot.cli build plot.txt -o build/mine --asset-base github
# hosting pictures at https://raw.githubusercontent.com/<owner>/<repo>/<branch>/…
```

That rewrites every local path to its `raw.githubusercontent.com` URL, derived
from your `origin` remote and current branch. Anywhere else works too:

```bash
# any CDN or bucket you have uploaded to
--asset-base https://cdn.example.com/run7

# or name each URL individually
--asset-map urls.json     # {"photos/01.jpg": "https://cdn.example.com/a.jpg"}
```

Without one of those, the brief marks each picture `!! UNHOSTED LOCAL FILE !!`
and the CLI warns on stderr, so a render can't quietly go out with your images
missing. Pictures given as URLs in the plot are left alone either way.

## Use it

```bash
python3 -m tiktok_plot.cli build examples/coffee.txt -o build/coffee
# build/coffee/prompt.md  build/coffee/scenes.json  build/coffee/storyboard.html

python3 -m tiktok_plot.cli build examples/with-photos.txt -o build/photos --asset-base github
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
`/tiktok-video` skill does it end to end: paste your plot, and it saves your
pictures, builds the brief, authors a HyperFrames composition under `videos/`,
renders the MP4 locally, and hands it back.

Hosted HyperFrames `compose` is disabled for CLI agents, so the skill renders
with the local HyperFrames CLI instead. That needs `ffmpeg` and a headless
Chrome (`npx hyperframes browser ensure`), and it means the composition is
plain HTML you can edit, diff and re-render. `videos/coffee-shop/` is a worked
example. To drive the hosted product instead, paste `prompt.md` into
HyperFrames on the web with the URLs from `--asset-base github`.

The brief pins down the things a video agent otherwise guesses: canvas size,
scene order, per-scene duration, and the exact on-screen copy (marked verbatim,
so your lines don't get "improved"). Scenes with your own picture say so in
three ways — use it exactly as provided, don't regenerate or restyle it, and
never substitute stock imagery — because a video agent handed a URL will
otherwise treat it as a suggestion. The brief also reserves the bottom 15% and
right 12% of frame, where TikTok's own UI sits.

The storyboard shows your actual pictures, inlined as data URIs so the HTML is
one portable file you can open or send anywhere.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Layout

| Path | What it is |
| --- | --- |
| `tiktok_plot/parser.py` | Plot text → `Plot`/`Scene` objects |
| `tiktok_plot/hosting.py` | Local picture paths → public `raw.githubusercontent.com` URLs |
| `tiktok_plot/prompt.py` | `Plot` → HyperFrames brief |
| `tiktok_plot/storyboard.py` | `Plot` → standalone HTML preview |
| `tiktok_plot/cli.py` | `prompt` / `parse` / `storyboard` / `build` |
| `.claude/skills/tiktok-video/` | The `/tiktok-video` Claude Code skill |
| `examples/coffee.txt` | A worked example, all pictures described |
| `examples/with-photos.txt` | A worked example using supplied pictures |
| `plots/coffee-shop.txt` | A real plot with five supplied photos |
| `videos/coffee-shop/` | The HyperFrames composition rendered from it |
