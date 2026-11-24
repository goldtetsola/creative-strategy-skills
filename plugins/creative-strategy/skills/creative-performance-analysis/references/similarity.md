# Similarity: repetition and range

Use this whenever the analysis covers two or more ads, asked about or not. It finds which ads repeat what they say (psychological similarity) or how they look (visual similarity), and what to change. The result goes in the output as its own short note, only when something in it can be acted on. Don't fold it into the per-ad findings. The comparison behind the note is working evidence; show it only when the user asks.

## 1. Describe each ad the same way

Record how each ad looks: format, setting, who is on screen and the opening shot. Record what it says: the buyer it speaks to, its claim and its proof, each with the quote or timestamp. Write "not shown" for any of those the ad doesn't contain. Also record the feeling the ad is built to prime and whether it frames its benefit as a gain or an avoided loss, by [reading the appeal](reading-the-appeal.md). Those two always get an answer, with quoted words.

Read a full capture of each video ([video capture](video-capture.md)), not a quick one. Take times from the capture and check them against the video's measured length. A time in the first 10 seconds rests on a frame you viewed. Use the terms in [the change vocabulary](#the-change-vocabulary) below so the same two ads always get the same description.

Ad names and titles back up what you read. They never decide what an ad says or what a test is for. The test purpose comes from the user or a test record: ads made to isolate one change, such as the same visuals with different opening lines, or to repair an error, overlap on purpose.

## 2. Check the footage

For video ads, run the bundled tool on the batch, from this skill's folder:

```bash
python3 scripts/ad_footage_overlap.py VIDEO VIDEO ... --out DIR
```

Use absolute video and output paths. DIR must sit outside this skill's folder, for example beside the user's ads; the tool refuses to write inside the skill. It needs `ffmpeg` and `ffprobe`. If they're missing, offer to install them with the one command for the user's system (`brew install ffmpeg` on macOS, `winget install ffmpeg` on Windows, the package manager on Linux) and run it on their yes; until then, compare openings and footage by eye from frames and captures. Keep DIR to compare a later batch without the old videos: give the tool the `.json` files from `DIR/assets` in place of the videos.

Each pair gets two rows. The opening is the first 3 seconds, closely. The body is the whole video. A row says match when at least 4 frames line up and at least half of them, and at least 3, are the same picture. A match means the two share footage, and the shift says how far apart the matching moments sit. The body row also says whether the two are the same video (at least half of each video's frames line up and the shorter is at least four-fifths as long as the longer), one sits inside the other, or only part is shared. Look at the images to see what is left over before you call it one ad. "Same shapes, different colour" means the picture matches and the colours differ. Look at the image and decide whether it is a grade, which is a small change, or a new palette, which isn't.

Look before you say "same". Open the images in `DIR/views`: matched frames side by side, and the first 10 seconds of each video. If you can't view images, say what the tool found and where, and don't say "same". The settings behind a match were checked on labelled videos, where no pair of different videos matched. They are still experimental, so a match is a candidate that the images confirm. A match against a fingerprint file whose video is gone has no image: the tool says so, and you don't call it "same". Never quote the tool's numbers to the user.

"Searched, found no match" is all a miss means. The tool can't see crops of 10% or more, mirrored or reversed footage, or a copy shifted by more than 2 seconds beyond the difference in length, and heavy text can hide a match. It also misses one ad resized for another placement: a square and a vertical version of the same ad did not match in the pairs checked. When two videos differ in shape, look at their images yourself. "Could not check" means that video or part wasn't compared. Name which, and make no call on it. If the tool didn't run, for example because ffmpeg is missing, say you couldn't compare the videos themselves and compare from the captures.

## 3. Make the call

You inspected the ads, so what they say and show is a fact you report, not a guess. Cite the element that is the same, such as the line, the footage or the opening shot. Say only what the check supports:

- A match on the opening row is "same opening". Call it one ad or the same video only when the body is the same too. Two ads that share an opening and differ after it are not one ad. A video found inside a longer one is inside it. When the tool finds no match but frames you pulled and viewed show the same footage under heavy text, say so and say you checked by eye.
- When every difference is on the small-change list below (text overlay only, colour grade only, voiceover edit only, a trim with no new first frame), say they are the same video with only that change. A new format, person, setting or framing is a larger change. Name what differs and don't count changes: a count of changed elements doesn't establish distinctness.
- The same video with words that change what the ad says compares the words, not a new idea. Say that. A deliberate wording test is valid when the user or a test record says so.
- **Psychological similarity:** two ads make the same argument when they make the same promise and offer the same thing, a gain or a loss avoided. The offer alone never groups ads. A group is what every member shares: two ads that are each close to a third are not close to each other. An ad read as Mixed on gain and loss groups with neither side, not even with another Mixed ad.
- Keep the feeling an ad is built to prime in the working evidence. Readers can differ on it, so name it in the note, in plain words rather than the motivation's name, only when the user asks or when a feeling none of the ads prime is the gap the next move fills. Say what the ad sets up, never what a viewer feels.

## Why range matters

An account reaches more buyers when its ads differ in who they speak to (the buyer and their situation), what that buyer already knows, the angle or promise, the feeling and frame, and how the ad looks and is made. Ads that repeat each other speak to the same buyer in the same way, so the account has fewer real ways in than its ad count suggests, and a result only shows which version of one idea won. Say that risk plainly, in the buyer's terms. Don't cite the ad platform's guidance or say how it grouped or delivered these ads. Give no similarity score or percentage and make no spend prediction. With account data, one plain sentence may say where spend or orders went in a stated period, as an observation and never as proof or cause.

## 4. What the note says

Say three things: where the ads repeat each other, in what they say, how they look or both; what that costs the account in reach, in the buyer's terms (who keeps hearing the same thing, and who never hears anything); and the gap the next shoot should fill, a buyer, situation, angle, feeling or format none of the ads covers yet. Name the ads, quote the line, give the time. Leave out ads that stand alone, unless one is the gap.

The move follows what the ads share. If they share what they say, change the proof or the buyer, because a new face won't fix it. If they share how they look, change the format, setting or person, because a new line won't fix it. If they share both, change both. If the overlap is a deliberate isolation test or a repair, say so and recommend no change. Ads that share what they say compete as versions of it, so a result shows which version wins, not whether the message beats a different one.

A finding needs the specific fact, what it means for the user, and what to do. Write no ad copy of your own and no invented numbers. If a launched batch has no overlap and nothing is missing, say nothing unless the user asked about diversity; then one line is enough. State what the note compared against when that changes the call.

## 5. When you can't tell

If no media for an ad could be inspected, say in the note which ad, say you couldn't do a proper similarity check, and ask for it. Make no call about that ad. An ad with one inspected video counts as inspected. Another video file listed for it is usually the same creative in another placement, so leave it out unless it would change the finding.

**Complete when:** every call rests on described media and a viewed match, the note names what it compared against when that changes the call, and the user can see what to change and which ads to leave alone.

## The change vocabulary

These definitions keep descriptions consistent. They describe how large a visible change is; they are not a platform finding about how Meta classifies ads.

### Video

**Major visible changes**

- **Format change** (static <-> video; other container changes only when their distinctness is evidenced)
- **New talent/creator** (new face/voice on screen)
- **New environment/context** (different setting/lighting/composition)
- **Major framing shift** (product-only <-> lifestyle; close-up <-> full scene)

**Moderate changes**

- **First-frame visual change** (opening shot clearly different)
- **Narrative structure** (reverse/reorder/tempo)
- **Audio signature** (new music/VO energy/ambience)
- **Lighting/color palette** (obvious, not subtle)

**Small changes** (they do not make a different video): text overlay only; colour grade only; VO edit only; trim without first-frame change; minor trims; transitions.

Definitions:

- Format: static -> video is a larger change. 16:9 -> 9:16 only is a small change (aspect ratio != format).
- Talent: a completely different person on screen, or a clearly different voice-over artist with no on-camera person, is a larger change. The same person in a new outfit is wardrobe, a small change.
- Environment: indoor -> outdoor, home -> commercial space, daytime -> night (visibly obvious) and polished studio -> casual setting are clear shifts. Kitchen -> living room in the same house is a medium shift. The same kitchen from a different corner, the same park from another angle, or cosmetic background tweaks are usually insufficient alone.
- Framing: product flat-lay -> human using the product, tight close-up -> full lifestyle scene, and static centre frame -> dynamic action shot are larger changes. Medium shot -> slightly closer medium shot is small.

### Static

**Major visible changes**

- **Format change** (single image <-> video; static <-> collection; other container changes only when their distinctness is evidenced)
- **New talent/model** (different person/face if human-focused)
- **New environment/background** (different setting/context/scene)
- **Major framing shift** (product-only <-> lifestyle; flat-lay <-> in-use; close-up <-> full scene)
- **Visual medium shift** (photo <-> illustration; realistic <-> graphic design)

**Moderate changes**

- **Primary visual element swap** (main product image/hero visual completely different)
- **Layout/compositional structure** (vertical <-> horizontal; grid <-> centered; left-heavy <-> right-heavy)
- **Color palette overhaul** (monochrome <-> vibrant; warm <-> cool; obvious, not subtle)
- **Visual density shift** (minimal clean <-> dense/busy; white space <-> filled)
- **Typography system change** (if visually dramatic: serif <-> sans; vintage <-> modern; large display <-> small text-heavy)
- **Copy-to-visual ratio** (image-dominant <-> text-dominant)

**Small changes** (they do not make a different ad): headline/copy changes only with the same visual; button colour; font size; subtle colour grade; minor element repositioning; the same image with a different crop only; border or corner radius.

Definitions:

- Format: static image -> video and photo -> collection are larger changes. Square (1:1) -> portrait (4:5) alone is small unless it forces a major redesign.
- Talent: a completely different person, or human-focused -> product-only (or the reverse) when the person was the primary element, is a larger change. The same person in a different outfit or pose is styling, a small change.
- Environment: studio/white background -> real-world setting, indoor -> outdoor, home -> commercial space, urban -> nature and product-only shot -> contextual scene are clear shifts. Kitchen -> living room, or one outdoor setting -> another, is a medium shift. The same room from a different corner, the same backdrop with different props, white -> light grey studio, or the same location from another angle are usually insufficient alone.
- Framing: flat-lay -> person using or wearing the product, close-up detail -> full scene, product-centred -> benefit/result-centred, and single product -> lifestyle tableau are larger changes. A slightly tighter crop is small.
- Visual medium: photography -> illustration, realistic render -> stylised, product photo -> infographic, and flat design -> 3D are larger changes. A photo filter change alone is small.
