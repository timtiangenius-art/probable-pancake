---
name: tiktok-video
description: Turn a plain-text TikTok plot (one line = one picture with on-screen text) into a rendered TikTok video via HyperFrames, using the user's own pictures when they supply them. Use when the user pastes a multi-line plot, script, or shot list — with or without attached images — and wants a short vertical video made from it.
---

# TikTok plot → video

The user supplies a plot where **each line is one scene**: one picture with text
on it. They may also supply the pictures. This skill parses that plot, hosts the
pictures, builds a HyperFrames brief, and renders it.

## Steps

1. **Save the plot.** Write what the user pasted to `plots/<slug>.txt`. Keep
   their wording exactly — the on-screen text is their copy, not yours. Add
   front matter only for settings they actually stated.

2. **Place their pictures.** If they attached or pointed at images, put them in
   `plots/<slug>-photos/` and reference each from its line after a `|`, in the
   order they gave. Match pictures to lines by their stated order or filename,
   and if the mapping is genuinely ambiguous, ask rather than guessing — a
   picture on the wrong line is worse than a question. Pictures already given as
   `https://` URLs need no copying.

3. **Build the brief.** Local pictures must be reachable over HTTPS before
   composing, so host them first when there are any:

   ```bash
   git add plots/ && git commit -m "Add plot and photos" && git push -u origin <branch>
   python3 -m tiktok_plot.cli build plots/<slug>.txt -o build/<slug> --asset-base github
   ```

   `--asset-base github` derives `raw.githubusercontent.com` URLs from the
   origin remote and current branch, and only works once the images are pushed
   **and the repo is public**. If it is private, upload the images elsewhere and
   pass that prefix instead (`--asset-base https://…`) or map them one by one
   with `--asset-map urls.json`. With no supplied pictures, drop the flag.

   This writes `prompt.md` (the HyperFrames brief), `scenes.json`, and
   `storyboard.html`.

4. **Sanity-check.** Read `prompt.md`. Confirm the scene count matches the
   number of lines they gave, every line's text is present verbatim, and each
   picture sits on the right line. Two things block a render outright:

   * `!! UNHOSTED LOCAL FILE !!` in the brief — the hosting step did not happen.
   * A `picture not found` warning — the path is wrong.

   Fetch one of the image URLs (`curl -sSI <url>`) to confirm it really is
   public before spending a render.

5. **Render it.** Hosted HyperFrames `compose`/`render_video` are **disabled for
   Claude Code** (and every CLI/IDE agent) — the MCP rejects them and points at
   the local skills. So render locally with the HyperFrames CLI, which also
   means local picture paths work directly and hosting is only needed if you
   want the images reachable from elsewhere.

   One-time environment setup (this container ships neither):

   ```bash
   apt-get update -qq && apt-get install -y -qq ffmpeg   # Playwright's ffmpeg is VP8-only
   npx -y hyperframes@latest browser ensure              # headless Chrome for rendering
   ```

   Then scaffold, author, gate, and render:

   ```bash
   cd videos && npx -y hyperframes@latest init <slug> --non-interactive \
     --example=blank --resolution=portrait
   cd <slug> && cp ../../plots/<slug>-photos/* assets/
   # author index.html per the contract below
   npx -y hyperframes@latest check                       # must be 0 errors
   npx -y hyperframes@latest snapshot --at <midpoints>   # then read contact-sheet.jpg
   npx -y hyperframes@latest render --quality high --output <slug>.mp4
   ffprobe -v error -show_entries format=duration -show_entries stream=width,height <slug>.mp4
   ```

   **`cdn.jsdelivr.net` is blocked by the egress proxy**, so the scaffold's GSAP
   `<script>` tag fails silently and nothing animates. Vendor it instead:
   `npm pack gsap@3.14.2`, extract `package/dist/gsap.min.js` to `vendor/`, and
   point the tag at the local copy. Do the same for fonts —
   `fonts.googleapis.com` and `fonts.gstatic.com` *do* work, so fetch the woff2
   and serve it from `vendor/` via `@font-face`. Take the **latin** subset, not
   the first `@font-face` in the CSS (that one is Vietnamese).

   Composition contract, in short: a sized root `<div>` carrying
   `data-composition-id`/`data-width`/`data-height`/`data-duration`; one
   `class="clip"` section per scene with `data-start` and `data-duration`; and
   exactly one paused GSAP timeline registered on
   `window.__timelines["<composition-id>"]`. Never pair a CSS `transform` with a
   GSAP tween on the same property — use `fromTo` so the start state lives in
   the tween. Never tween `display`/`visibility` on a clip element. A Ken Burns
   push-in trips the layout audit, so mark those images
   `data-layout-allow-overflow`.

   Landscape photos in a 9:16 frame: `object-fit: cover` crops a 16:9 source to
   its centre ~31%, which throws away most of the shot. Use `contain` over a
   blurred copy of the same image, with `object-position: center 64%` so the
   caption owns the space above rather than leaving dead blur below.

6. **Deliver.** Send the MP4 and the storyboard so they can see how their
   pictures were used. Say plainly that the render is silent: HyperFrames has no
   music unless a track is supplied, and for TikTok that is correct anyway —
   creators add audio in the app, where the in-app track drives reach. Tell them
   the timestamp their beat should drop on.

## Edits

Re-running the pipeline on an edited plot file and composing again with the same
`projectId` applies the change to the existing project rather than making a new
one. Prefer that over starting over. Swapping a picture means replacing the file
and pushing again — the URL stays the same, so re-compose to pick it up, or use
a new filename to sidestep any caching.

## Why the brief still matters when rendering locally

`prompt.md` is no longer pasted into a hosted agent, but it stays the spec you
author against: it is where the scene order, the per-scene durations, the
verbatim copy and the safe margins are pinned down. Read it before writing the
HTML and check the finished composition back against it.

If the user would rather drive HyperFrames themselves — or wants a hosted
project with a shareable `app.heygen.com` link, which the local path does not
produce — hand them `build/<slug>/prompt.md` to paste into HyperFrames on the
web, along with the hosted image URLs from `--asset-base github`.
