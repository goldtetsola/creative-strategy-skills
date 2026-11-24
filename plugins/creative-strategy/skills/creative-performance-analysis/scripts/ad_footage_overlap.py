#!/usr/bin/env python3
"""Measure how much footage two or more ad videos share.

Each video gets a small fingerprint: a 64-bit shape hash and a coarse colour signature for sampled frames,
at 0.25 s steps over the first 3 seconds (the opening) and at 1 s steps over the whole video (the body).
Every pair is compared in both rows at the best constant time shift, counting matches over the frames that
overlap and are not near-uniform. A match is a candidate: look at the images the tool writes before saying
"same". Uses only ffmpeg, ffprobe and the standard library.

Writes under --out (any folder outside this skill's own files): assets/ holds one fingerprint file per video, keyed by
the sha256 of its bytes and the sampling settings; views/ holds a first-10-seconds contact sheet per video
and a side-by-side image of matched frames for each matching row.

The tool cannot see crops of 10% or more, mirrored or reversed footage, or a copy shifted by more than
2 seconds beyond the difference in length. "No match" never means the footage is different.
Exit code 0 means every row was checked and every image that could be made was written; 2 means something could
not be checked or written. A match against a fingerprint file whose video is no longer on disk gets no side-by-side
image: the output says so, and the match is not to be called "the same" without viewing the footage.
"""
import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GRID = 32                                   # grayscale frame size the shape hash is taken from
OPEN_OFFSET, OPEN_STEP, OPEN_SECONDS = 0.125, 0.25, 3.0
BODY_OFFSET, BODY_STEP = 0.5, 1.0
SETTINGS = {"version": 1, "grid": GRID, "opening": [OPEN_OFFSET, OPEN_STEP, OPEN_SECONDS], "body": [BODY_OFFSET, BODY_STEP]}
SETTINGS_ID = hashlib.sha1(json.dumps(SETTINGS, sort_keys=True).encode()).hexdigest()[:8]
# Starting values from the prototype, experimental until calibrated on held-out media.
SHAPE_BITS = 12        # most differing bits (of 64) that still count as the same picture
COLOUR_GUARD = 0.10    # mean colour difference (0 to 1) allowed on a match
FLAT = 6.0             # frames flatter than this (grayscale spread) carry no shape and are skipped
MIN_USABLE = 4         # usable overlapping frames needed before a row can say anything
SHARE = 0.5            # share of usable overlapping frames that must match
SAME_LENGTH = 0.8      # the shorter video must be at least this share of the longer one to be called the same video
MIN_MATCHED = 3        # and at least this many must match, so a brief overlap at the edge of the shift range is not a match
OPENING_SHIFT_SECONDS = 2.0
BLIND_SPOTS = ("crops of 10% or more, mirrored or reversed footage, and copies shifted by more than "
               "2 seconds beyond the difference in length")
IMAGE_BYTES = 10_000   # images stay under this size so an agent host can open them
IMAGE_STEPS = [(96, 6), (96, 14), (80, 14), (64, 14), (64, 24), (48, 31)]   # tile width, JPEG quality (lower is better)


class CouldNotCheck(Exception):
    pass


def run(cmd, what):
    try:
        # ffmpeg writes UTF-8 paths in its messages; the platform default (cp1252 on Windows) cannot always decode them.
        done = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise CouldNotCheck(f"{cmd[0]} is not installed")
    if done.returncode:
        raise CouldNotCheck(f"{what} failed: {(done.stderr.strip() or 'no message')[:160]}")
    return done.stdout


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


_DCT = [[math.cos(math.pi * (2 * n + 1) * k / (2 * GRID)) for n in range(GRID)] for k in range(8)]


def shape_hash(gray):
    """64-bit hash of the 8x8 low-frequency DCT block of a GRIDxGRID grayscale frame (bytes)."""
    rows = [gray[r * GRID:(r + 1) * GRID] for r in range(GRID)]
    half = [[sum(_DCT[k][r] * rows[r][c] for r in range(GRID)) for c in range(GRID)] for k in range(8)]
    block = [round(sum(half[k][c] * _DCT[m][c] for c in range(GRID)), 6) for k in range(8) for m in range(8)]
    middle = statistics.median(block[1:])
    return sum(1 << (63 - i) for i, value in enumerate(block) if value > middle)


def probe(path):
    if not path.is_file():
        raise CouldNotCheck("file not found")
    if path.stat().st_size == 0:
        raise CouldNotCheck("empty file")
    info = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                           "-of", "json", str(path)], "reading the video"))
    if "video" not in [s.get("codec_type") for s in info.get("streams", [])]:
        raise CouldNotCheck("no video stream")
    duration = float(info.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise CouldNotCheck("zero-length video")
    return duration


def sample(path, start, step, seconds=None):
    """Frames at start, start+step, ... as (shape hash, colour bytes, spread), from one ffmpeg run."""
    with tempfile.TemporaryDirectory(prefix="ad-footage-") as tmp:
        gray, colour = Path(tmp) / "gray.raw", Path(tmp) / "colour.raw"
        graph = (f"[0:v:0]fps={1 / step:g},split[a][b];"
                 f"[a]scale={GRID}:{GRID}:flags=lanczos,format=gray[g];[b]scale=4:4:flags=area,format=rgb24[c]")
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(start)] + (["-t", str(seconds)] if seconds else [])
        cmd += ["-i", str(path), "-filter_complex", graph, "-map", "[g]", "-f", "rawvideo", str(gray),
                "-map", "[c]", "-f", "rawvideo", str(colour)]
        run(cmd, "extracting frames")
        gray_bytes, colour_bytes = gray.read_bytes(), colour.read_bytes()
    count, size = len(gray_bytes) // GRID ** 2, GRID ** 2
    if count == 0 or count != len(colour_bytes) // 48:
        raise CouldNotCheck("no frames could be read")
    return [(shape_hash(gray_bytes[i * size:(i + 1) * size]), colour_bytes[i * 48:(i + 1) * 48],
             statistics.pstdev(gray_bytes[i * size:(i + 1) * size])) for i in range(count)]


def encode(frames):
    return [{"h": f"{h:016x}", "c": c.hex(), "v": round(v, 3)} for h, c, v in frames]


def decode(rows):
    return [(int(r["h"], 16), bytes.fromhex(r["c"]), r["v"]) for r in rows]


def fingerprint(path, assets):
    """The asset's fingerprint file, made once per (source bytes, settings). Returns the decoded asset."""
    if not path.is_file():
        raise CouldNotCheck("file not found")
    digest = sha256_file(path)
    target = assets / f"{digest}.{SETTINGS_ID}.json"
    if not target.exists():
        data = {"settings": SETTINGS, "source_sha256": digest, "source_path": str(path.resolve()), "name": path.stem,
                "bytes": path.stat().st_size,
                "duration_s": round(probe(path), 3),
                "opening": encode(sample(path, OPEN_OFFSET, OPEN_STEP, OPEN_SECONDS)),
                "body": encode(sample(path, BODY_OFFSET, BODY_STEP))}
        assets.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".partial")
        partial.write_text(json.dumps(data))
        os.replace(partial, target)
    asset = load_fingerprint(target, path)
    asset["name"] = path.stem      # the file may share its bytes with a differently named one
    return asset


def load_fingerprint(file, source=None):
    data = json.loads(Path(file).read_text())
    if data.get("settings") != SETTINGS:
        raise CouldNotCheck("fingerprint file was made with different settings")
    if not isinstance(data.get("duration_s"), (int, float)) or data["duration_s"] <= 0:
        raise CouldNotCheck("fingerprint file has no usable duration")
    original = source if source is not None else Path(data.get("source_path", ""))
    present = original.is_file()
    if present and data["source_sha256"] != sha256_file(original):
        raise CouldNotCheck("the video changed since this fingerprint file was made")
    # A video still at its recorded path, checked against the file's checksum, is a valid source for images.
    return {"name": data["name"], "sha256": data["source_sha256"], "duration_s": data["duration_s"],
            "opening": decode(data["opening"]), "body": decode(data["body"]), "source": original if present else None}


def distance(a, b):
    return bin(a ^ b).count("1")


def colour_distance(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / (len(a) * 255)


def usable(frame):
    return frame[2] >= FLAT


def same_picture(a, b):
    return distance(a[0], b[0]) <= SHAPE_BITS and colour_distance(a[1], b[1]) <= COLOUR_GUARD


def same_shapes(a, b):
    return distance(a[0], b[0]) <= SHAPE_BITS


def best_shift(a, b, max_shift, agree):
    """Best constant shift s with a[i] ~ b[i+s] over usable overlapping frames.

    Among shifts that pass the match rule, the one that lines up the most frames, then the smallest shift, so a
    short overlap where every frame agrees cannot beat the true alignment on near-static footage. If no shift
    passes, the one with the highest share of agreeing frames (the caller then reports no match)."""
    found = []
    for s in range(-max_shift, max_shift + 1):
        pairs = [(i, i + s) for i in range(len(a)) if 0 <= i + s < len(b) and usable(a[i]) and usable(b[i + s])]
        if len(pairs) < MIN_USABLE:
            continue
        hits = [(i, j) for i, j in pairs if agree(a[i], b[j])]
        found.append(((len(hits) / len(pairs), len(hits), -abs(s)), s, hits, len(pairs)))
    if not found:
        return None
    passing = [f for f in found if enough(f[2], f[3])]
    if passing:
        return max(passing, key=lambda f: (len(f[2]), -abs(f[1]), f[0][0]))
    return max(found, key=lambda f: f[0])


def enough(hits, usable_count):
    return len(hits) >= MIN_MATCHED and len(hits) / usable_count >= SHARE


def compare_row(a, b, max_shift, step, offset, relation=False, length_ratio=1.0):
    found = best_shift(a, b, max_shift, same_picture)
    if found is None:
        return {"status": "could not check", "reason": f"fewer than {MIN_USABLE} usable frames overlap"}
    status, (_, s, hits, usable_count) = "match", found
    if not enough(hits, usable_count):
        shapes = best_shift(a, b, max_shift, same_shapes)
        if shapes and enough(shapes[2], shapes[3]):
            status, (_, s, hits, usable_count) = "same shapes, different colour", shapes
        else:
            status = "no match"
    row = {"status": status, "shift_s": round(s * step, 3), "matched": len(hits), "usable": usable_count}
    if status == "no match":
        return row
    if relation:
        a_cover, b_cover = len(hits) / sum(map(usable, a)), len(hits) / sum(map(usable, b))
        if min(a_cover, b_cover) >= SHARE:
            row["relation"] = "same" if length_ratio >= SAME_LENGTH else "a inside b" if len(a) < len(b) else "b inside a"
        else:
            row["relation"] = "a inside b" if a_cover >= SHARE else "b inside a" if b_cover >= SHARE else "partly shared"
    if status == "same shapes, different colour":
        row["colour_distance"] = round(sum(colour_distance(a[i][1], b[j][1]) for i, j in hits) / len(hits), 3)
    chosen = [hits[round(k * (len(hits) - 1) / max(min(len(hits), 4) - 1, 1))] for k in range(min(len(hits), 4))]
    row["view"] = [(round(offset + i * step, 3), round(offset + j * step, 3)) for i, j in chosen]
    return row


def compare(a, b):
    return {"opening": compare_row(a["opening"], b["opening"], round(OPENING_SHIFT_SECONDS / OPEN_STEP),
                                   OPEN_STEP, OPEN_OFFSET),
            "body": compare_row(a["body"], b["body"], abs(len(a["body"]) - len(b["body"])) + 2,
                                BODY_STEP, BODY_OFFSET, relation=True,
                                length_ratio=min(a["duration_s"], b["duration_s"]) / max(a["duration_s"], b["duration_s"]))}


def tile_fit(tile):
    height = round(tile * 16 / 9) // 2 * 2
    return f"scale={tile}:{height}:force_original_aspect_ratio=decrease,pad={tile}:{height}:(ow-iw)/2:(oh-ih)/2"


def tile_chain(inputs, tile):
    """ffmpeg filter graph that scales each input to one tile size, then joins them in rows of two."""
    parts = [f"[{n}:v]{tile_fit(tile)}[t{n}]" for n in range(inputs)]
    rows = [f"[t{n}][t{n + 1}]hstack=inputs=2[r{n // 2}]" for n in range(0, inputs, 2)]
    count = inputs // 2
    tail = f"{''.join(f'[r{n}]' for n in range(count))}vstack=inputs={count}[o]" if count > 1 else "[r0]null[o]"
    return ";".join(parts + rows + [tail])


def write_image(target, make):
    """Write the image with the largest tiles and best quality that keep it under IMAGE_BYTES."""
    for tile, quality in IMAGE_STEPS:
        make(tile, quality)
        if target.stat().st_size <= IMAGE_BYTES:
            return
    raise CouldNotCheck(f"image is over {IMAGE_BYTES} bytes at the smallest size")


def write_pair_view(a_path, b_path, moments, target):
    def make(tile, quality):
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for ta, tb in moments:
            cmd += ["-ss", str(ta), "-i", str(a_path), "-ss", str(tb), "-i", str(b_path)]
        run(cmd + ["-filter_complex", tile_chain(2 * len(moments), tile), "-map", "[o]", "-frames:v", "1",
                   "-q:v", str(quality), "-update", "1", str(target)], "writing the side-by-side image")
    write_image(target, make)


def write_sheet(path, target):
    def make(tile, quality):
        run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-t", "10", "-i", str(path), "-vf",
             f"fps=1,{tile_fit(tile)},tile=5x2", "-frames:v", "1", "-q:v", str(quality), "-update", "1",
             str(target)],
            "writing the contact sheet")
    write_image(target, make)


def describe(row):
    status = row["status"]
    if status == "could not check":
        return f"could not check ({row['reason']})"
    if status == "no match":
        return f"searched, found no match (the tool cannot see {BLIND_SPOTS})"
    when = "at the same time" if row["shift_s"] == 0 else (
        f"{abs(row['shift_s']):g} s {'later' if row['shift_s'] > 0 else 'earlier'}")
    base = f"{row['matched']} of {row['usable']} frames, matching moments sit {when} in the second video"
    if status == "same shapes, different colour":
        return f"same shapes, different colour ({base}, colour distance {row['colour_distance']})"
    return f"match{': ' + row['relation'] if 'relation' in row else ''} ({base})"


def inside_repo(folder):
    resolved = Path(folder).resolve()
    return resolved == REPO or REPO in resolved.parents


TEMP_FALLBACKS = ("/tmp", "/var/tmp", "/usr/tmp")


def folder_in_repo(out):
    """The first output folder that resolves into this skill's own files, symlinks included."""
    for folder in ([out, out / "assets", out / "views"] if out else []):
        if inside_repo(folder):
            return folder


def choose_temp_folder():
    """Pin tempfile to a usable folder outside the repository; return None, or why the tool must not run.

    tempfile.gettempdir() tests a folder by writing a file into it and falls back to the current directory, which
    can be the repository. This picks the folder without writing anywhere, and a folder named by TMPDIR, TEMP or
    TMP that is inside the repository is refused rather than skipped.
    """
    named = [Path(os.environ[name]) for name in ("TMPDIR", "TEMP", "TMP") if os.environ.get(name)]
    for folder in named:
        if inside_repo(folder):
            return f"refusing to write fingerprints or images inside the repository ({folder})"
    for folder in (*named, *map(Path, TEMP_FALLBACKS)):
        if folder.is_dir() and os.access(folder, os.W_OK | os.X_OK) and not inside_repo(folder):
            tempfile.tempdir = str(folder.resolve())
            return None
    return "no temporary folder outside the repository is usable"


def file_name_safe(name):
    """A label is part of an image's file name. A fingerprint file chooses its own name, so remove the separators
    and Windows drive or stream markers that would let it move an image out of the checked folder, and the
    characters Windows refuses in file names."""
    return "".join("_" if char in '/\\:<>"|?*' or ord(char) < 32 else char for char in str(name))


def name_key(name):
    """Compare names without case or Unicode composition differences."""
    return unicodedata.normalize("NFD", unicodedata.normalize("NFD", name).casefold())


def unique_label(name, taken):
    """A label no earlier asset in the batch has under name_key, so its image file names cannot collide either.
    taken holds the keys of the labels so far and gains the new one."""
    label, number = name, 1
    while name_key(label) in taken:
        number += 1
        label = f"{name}-{number}"
    taken.add(name_key(label))
    return label


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("assets", nargs="+", help="video files, or fingerprint .json files from an earlier run")
    parser.add_argument("--out", help="folder for fingerprint files and images (default: a new temporary folder)")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve() if args.out else None
    inside = folder_in_repo(out)
    problem = (f"refusing to write fingerprints or images inside the repository ({inside}); use a folder outside "
               f"this skill's own files") if inside \
        else choose_temp_folder()
    if problem:
        print(f"could not check: {problem}")
        return 2
    out = out or Path(tempfile.mkdtemp(prefix="ad-footage-overlap-")).resolve()
    loaded, labels = [], set()
    for arg in args.assets:
        path = Path(arg)
        try:
            asset = load_fingerprint(path) if path.suffix == ".json" else fingerprint(path, out / "assets")
        except CouldNotCheck as error:
            asset = {"name": path.stem, "error": str(error)}
        except (OSError, ValueError, KeyError, AttributeError, TypeError) as error:
            asset = {"name": path.stem, "error": f"could not read it ({error.__class__.__name__})"}
        asset["label"] = unique_label(file_name_safe(asset["name"]), labels)
        loaded.append(asset)
    results, positions, failed = [], [], False
    for n, a in enumerate(loaded):
        for m, b in enumerate(loaded[n + 1:], n + 1):
            broken = a.get("error") or b.get("error")
            rows = ({k: {"status": "could not check", "reason": broken} for k in ("opening", "body")}
                    if broken else compare(a, b))
            failed |= any(r["status"] == "could not check" for r in rows.values())
            results.append({"a": a["label"], "b": b["label"], "rows": rows})
            positions.append((n + 1, m + 1))
    failed |= any("error" in a for a in loaded)
    notes = []
    views = out / "views"
    for asset in loaded:
        if asset.get("source"):
            try:
                views.mkdir(parents=True, exist_ok=True)
                write_sheet(asset["source"], views / f"{asset['label']}--first10s.jpg")
            except CouldNotCheck as error:
                notes.append(f"image not written for {asset['label']}: {error}")
                failed = True
    sources = {a["label"]: a.get("source") for a in loaded}
    written = set()
    for result, (first, second) in zip(results, positions):
        for name, row in result["rows"].items():
            if row["status"] not in ("match", "same shapes, different colour"):
                continue
            gone = [label for label in (result["a"], result["b"]) if not sources[label]]
            if gone:
                notes.append(f"no side-by-side image for {result['a']} and {result['b']} ({name}): the video for "
                             f"{' and '.join(gone)} is no longer available, so this match rests on its saved fingerprint "
                             f"file. Do not call it the same without viewing the footage")
                continue
            target = views / f"{result['a']}--{result['b']}--{name}.jpg"
            if name_key(target.name) in written:
                # Labels may contain "--", so two pairs can share a name; batch positions keep each pair's image.
                target = views / f"{result['a']}--{result['b']}--{name}--{first}-{second}.jpg"
            written.add(name_key(target.name))
            try:
                views.mkdir(parents=True, exist_ok=True)
                write_pair_view(sources[result["a"]], sources[result["b"]], row["view"], target)
            except CouldNotCheck as error:
                notes.append(f"image not written for {result['a']} and {result['b']} ({name}): {error}")
                failed = True
    if args.json:
        print(json.dumps({"out": str(out), "assets": [{k: a.get(k) for k in ("label", "sha256", "duration_s", "error")}
                                                      for a in loaded], "pairs": results, "notes": notes}, indent=1))
    else:
        for a in loaded:
            if "error" in a:
                print(f"{a['label']}: could not check ({a['error']})")
        for result in results:
            print(f"{result['a']} vs {result['b']}")
            for name, row in result["rows"].items():
                print(f"  {name}: {describe(row)}")
        for note in notes:
            print(note)
        print(f"fingerprint files are in {out / 'assets'}" + (f" and images in {views}" if views.is_dir() else ""))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
