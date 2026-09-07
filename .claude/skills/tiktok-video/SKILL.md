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

5. **Compose.** Pass the full contents of `prompt.md` as the `prompt` argument
   to `mcp__HyperFrames_by_HeyGen__compose`. Leave `projectId` empty for a new
   video; pass the previous `projectId` for an edit. Only set `designSource`
   when the user named a house style.

   `compose` returns immediately and renders in the background. Poll
   `mcp__HyperFrames_by_HeyGen__get_project_status` until `session_status` is
   `draft`/`completed`; if it goes to `waiting`, relay the agent's question to
   the user and send their answer back through another `compose` call.

6. **Deliver.** Send the storyboard alongside the video so they can see how
   their pictures were used. Give the user the video and the project link. If they ask for
   the MP4 URL, call `render_video` then `get_render_status` and put the
   `video_url` in the reply itself.

## Edits

Re-running the pipeline on an edited plot file and composing again with the same
`projectId` applies the change to the existing project rather than making a new
one. Prefer that over starting over. Swapping a picture means replacing the file
and pushing again — the URL stays the same, so re-compose to pick it up, or use
a new filename to sidestep any caching.

## If HyperFrames compose is unavailable

The HyperFrames MCP disables `compose`/`render_video` for some CLI clients. If a
call is rejected that way, say so plainly and offer the fallbacks: install the
local skills (`npx skills add heygen-com/hyperframes`), or hand the user
`build/<slug>/prompt.md` to paste into HyperFrames themselves. The storyboard
HTML is still worth sending either way.
