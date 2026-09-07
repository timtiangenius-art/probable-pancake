---
name: tiktok-video
description: Turn a plain-text TikTok plot (one line = one picture with on-screen text) into a rendered TikTok video via HyperFrames. Use when the user pastes a multi-line plot, script, or shot list and wants a short vertical video made from it.
---

# TikTok plot → video

The user supplies a plot where **each line is one scene**: one picture with text
on it. This skill parses that plot, builds a HyperFrames brief, and renders it.

## Steps

1. **Save the plot.** Write what the user pasted to `plots/<slug>.txt`. Keep
   their wording exactly — the on-screen text is their copy, not yours. Add
   front matter only for settings they actually stated.

2. **Build the brief.**

   ```bash
   python3 -m tiktok_plot.cli build plots/<slug>.txt -o build/<slug>
   ```

   This writes `prompt.md` (the HyperFrames brief), `scenes.json`, and
   `storyboard.html`.

3. **Sanity-check.** Read `prompt.md`. Confirm the scene count matches the
   number of lines they gave and that every line's text is present verbatim.
   If a line is missing, the plot has a syntax problem — fix it before spending
   a render.

4. **Compose.** Pass the full contents of `prompt.md` as the `prompt` argument
   to `mcp__HyperFrames_by_HeyGen__compose`. Leave `projectId` empty for a new
   video; pass the previous `projectId` for an edit. Only set `designSource`
   when the user named a house style.

   `compose` returns immediately and renders in the background. Poll
   `mcp__HyperFrames_by_HeyGen__get_project_status` until `session_status` is
   `draft`/`completed`; if it goes to `waiting`, relay the agent's question to
   the user and send their answer back through another `compose` call.

5. **Deliver.** Give the user the video, and the project link. If they ask for
   the MP4 URL, call `render_video` then `get_render_status` and put the
   `video_url` in the reply itself.

## Edits

Re-running the pipeline on an edited plot file and composing again with the same
`projectId` applies the change to the existing project rather than making a new
one. Prefer that over starting over.

## If HyperFrames compose is unavailable

The HyperFrames MCP disables `compose`/`render_video` for some CLI clients. If a
call is rejected that way, say so plainly and offer the fallbacks: install the
local skills (`npx skills add heygen-com/hyperframes`), or hand the user
`build/<slug>/prompt.md` to paste into HyperFrames themselves. The storyboard
HTML is still worth sending either way.
