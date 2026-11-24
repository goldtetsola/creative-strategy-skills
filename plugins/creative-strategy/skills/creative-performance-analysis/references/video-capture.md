# Capturing videos and images

The bundled script uploads a video to Gemini and saves a Markdown capture of what it says and shows. Statics are read with the host's own image vision. A capture is internal evidence for the analysis, not a deliverable.

## Choose the depth

Decide per video with one question: **will the analysis explain this video?** Explaining means saying why it earned or missed attention, spend or customers; what it does better or worse than another video; what to keep, change or borrow from it; or whether it repeats another video.

| The task needs to… | Depth |
|---|---|
| **Explain** the video: performance explanation, comparison, repetition note, next-step blueprint | **Full:** `--mode detailed` |
| **Know** what the video says and shows: a transcript, a caption or text list, an inventory, screening a batch to choose which videos to explain | **Quick:** `--mode quick` |
| Answer a narrow detail question: a faint phrase under music, separate voices or effects, exact visibility, object movement, spatial relationships or scene continuity | **Full**, even for a one-line answer |

Every video the analysis explains gets full capture, on both sides of a comparison: the top spender and the ad that got nothing. A batch can be screened with quick captures; each video then chosen for explanation gets full capture before any sentence explains it. A quick capture serves knowing tasks only.

The reason is coverage. Quick capture records visual events, speech and on-screen text with timestamps and visible uncertainty. Full capture adds separate voice, music and effects passes, a scene-by-scene account of cuts and transitions, exact visibility and motion, and the Ad Substance Summary. An explanation depends on those details.

Read the whole full capture before relying on it: timeline, audio, on-screen text and summary. The Ad Substance Summary is an index to the capture; the timeline and audio sections hold the evidence. A detailed output's check declarations are model claims, not independent verification. Check consequential ambiguities against the source. Neither mode proves an ad's cause of performance.

## Run

A capture uploads the video to Google's Gemini with the user's key, costs one API call per video, and leaves a Markdown capture beside the video. The script tries to delete the upload afterwards but cannot guarantee it. Before the first upload, tell the user which videos you'd send and how many, and get their yes. Reuse existing captures first. If they decline, explain only what inspected images and existing captures allow, and say which videos stay unexplained.

The script needs only Python 3.11 or later; there is nothing to install. Just run it. It finds the user's key itself, in `GEMINI_API_KEY` or `~/.config/creative-strategy/.env`. When it stops with `NEEDS_GEMINI_KEY` or `GEMINI_KEY_REJECTED`, it has already created that file and opened it in the user's text editor. Tell them in two short sentences: get a free key at https://aistudio.google.com/apikey, paste it after `GEMINI_API_KEY=` in the file that just opened, save, and reply "done". Then run the capture again. If the editor did not open, give them the file's path instead. Never ask for the key in chat, and never open, print or edit the key file. If they paste a key into chat anyway, don't repeat it; ask them to put it in the file. While you wait, carry on with the work that doesn't need the video.

```bash
python3 scripts/analyze_video.py "<video-path>" --mode detailed
python3 scripts/analyze_video.py "<video-path>" --mode quick
```

Run from this skill's folder, or give the script's absolute path. `--setup` checks the key with Gemini, without uploading anything, and reports whether `ffmpeg` is installed.

- Optional second positional argument: exact output file.
- Default output: `<video-dir>/Analyses/<video-filename>.<mode>.md`, keeping the input extension. `ad.mp4` becomes `ad.mp4.quick.md` or `ad.mp4.detailed.md`.
- `--model <id>` overrides the default, `gemini-2.5-flash`.
- `--refresh` captures again despite a reviewed match, when a known coverage limit calls for it.

Blank or abnormal responses fail without replacing a previous capture. Non-empty text and a normal finish do not prove factual accuracy or full coverage; read the result before relying on it. Do not bypass a provider refusal. Report unavailable evidence and continue independent captures. Invent no strategy or causal conclusion to fill a missing transcript.

For a batch, keep one result per input and mode, track each process's exit status and inspect its output; an output filename does not prove a successful capture.

## Review once, then reuse

Every new capture gets a `<capture>.capture.json` record beside it, marked **pending**. Its hashes bind the exact media bytes, instructions, mode, model and capture text. A reviewed capture of the same bytes, in the same mode, is reused automatically before any upload, if it sits in the output folder or the video's `Analyses/` folder; add `--reuse-root <folder>` to search a wider folder that contains the video. A pending capture is not reused until it is reviewed and accepted. Changed bytes, instructions, mode, model or capture text, and pending reviews, do not reuse.

After reading a capture and checking its decision-relevant speech, overlays, visuals and ambiguities against the original, accept it for reuse with the same video, output and mode:

```bash
python3 scripts/analyze_video.py "<video-path>" "<capture-path>" --mode detailed --accept-review "Checked source and full coverage; kept the relevant limits in the capture."
```

If you corrected the capture, register it again first with `--register-capture` and the same arguments, then accept it. Neither command uploads anything. Use a truthful note describing the check.

## Statics

Read each image with the host's native vision, from the actual file. If the host cannot inspect it, say so; do not infer content from the filename. Apply the purely visual method in [the image prompt](../scripts/prompts/image.md) before interpreting: describe what is there, mark cropped, obscured, unreadable or uncertain details, and keep strategy and persuasion out of the description. Interpretation happens afterwards, in the analysis.

## What the analysis may claim

Name the evidence actually used. A capture can support the details it preserves when the source version is verified and coverage is adequate; capture-only analysis must not claim direct viewing. Missing media limits only the details a verified capture cannot establish.
