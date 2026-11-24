"""Hash-bound, source-adjacent review records for reusable media captures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote


SUFFIX = ".capture.json"
REFERENCE = "<!-- media-capture-reference:v1 -->"
IMAGE_PROMPT = Path(__file__).resolve().parent / "prompts" / "image.md"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def contract(kind, mode, model, instructions):
    if not all(value.strip() for value in (kind, mode, model, instructions)):
        raise ValueError("Capture kind, mode, actual model identity and full prompt must be non-empty.")
    return {"kind": kind, "mode": mode, "model": model,
            "prompt_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest()}


def same_file(first, second):
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second)
    )


def metadata_path(capture):
    return capture.with_name(capture.name + SUFFIX)


def protect(media, capture, protected=()):
    inputs = [media, *protected]
    metadata = metadata_path(capture)
    if any(same_file(capture, path) or same_file(metadata, path) for path in inputs) or same_file(metadata, capture):
        raise ValueError("Capture and review record must be separate from media, prompt and each other, including aliases.")


def _atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                         prefix=".capture-record-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write(path, record):
    _atomic(path, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def register(media, capture, capture_contract, protected=(), content=None):
    """Record a pending capture, optionally before its atomic replacement."""
    protect(media, capture, protected)
    body = capture.read_bytes() if content is None else content
    if not body.strip():
        raise ValueError("An empty capture cannot be registered.")
    if body.lstrip().startswith(REFERENCE.encode("utf-8")):
        raise ValueError("A reuse reference is not a full capture; review the linked canonical capture instead.")
    record = {"version": 1, "source": os.path.relpath(media.resolve(), capture.parent.resolve()),
              "media_sha256": sha(media), "capture": capture.name,
              "capture_sha256": hashlib.sha256(body).hexdigest(),
              "contract": capture_contract, "reviewed": False}
    _write(metadata_path(capture), record)
    return record


def _matching(media_hash, capture, capture_contract):
    record = json.loads(metadata_path(capture).read_text(encoding="utf-8"))
    if (record.get("version") != 1 or record.get("capture") != capture.name
            or record.get("media_sha256") != media_hash or record.get("contract") != capture_contract
            or not isinstance(record.get("source"), str) or not record["source"]
            or not capture.is_file() or not capture.stat().st_size
            or record.get("capture_sha256") != sha(capture)):
        return None
    return record


def accept(media, capture, capture_contract, review_note, protected=()):
    """The caller must first perform the existing source and coverage checks."""
    protect(media, capture, protected)
    if not review_note.strip():
        raise ValueError("Describe the source/coverage review before accepting a capture.")
    record = _matching(sha(media), capture, capture_contract)
    if record is None:
        raise ValueError("Capture or source changed, or no matching pending record exists; register and review the current capture first.")
    record.update(reviewed=True, review_note=review_note.strip())
    _write(metadata_path(capture), record)
    return record


def lookup(media, capture, capture_contract, reuse_root=None, protected=()):
    """Return a reviewed exact match; malformed or stale records are misses."""
    protect(media, capture, protected)
    if reuse_root is not None:
        reuse_root = reuse_root.resolve()
        if not media.resolve().is_relative_to(reuse_root):
            raise ValueError("The reuse root must contain the requested media.")
        candidates = sorted(reuse_root.rglob("*" + SUFFIX))
    else:
        folders = {media.parent / "Analyses", capture.parent}
        candidates = sorted({path for folder in folders for path in folder.glob("*" + SUFFIX)
                             if path.resolve().is_relative_to(folder.resolve())})
    exact = metadata_path(capture)
    candidates = [exact, *(path for path in candidates if path != exact)]
    media_hash = sha(media)
    for metadata in candidates:
        if reuse_root is not None and not metadata.resolve().is_relative_to(reuse_root):
            continue
        candidate = metadata.with_name(metadata.name[:-len(SUFFIX)])
        try:
            protect(media, candidate, protected)
            record = _matching(media_hash, candidate, capture_contract)
            if record is not None and record.get("reviewed") is True and record.get("review_note", "").strip():
                return candidate, record
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return None


def materialize(media, output, match, protected=()):
    """Keep same-folder text; cross-folder outputs point to the canonical capture."""
    source, record = match
    if output.resolve() == source.resolve():
        return output
    protect(media, output, (*protected, source, metadata_path(source)))
    content = source.read_bytes()
    if hashlib.sha256(content).hexdigest() != record["capture_sha256"] or sha(media) != record["media_sha256"]:
        raise ValueError("Reviewed capture or media changed during reuse; review the current files.")
    if output.parent.resolve() != source.parent.resolve():
        reference = quote(os.path.relpath(source.resolve(), output.parent.resolve()).replace(os.sep, "/"), safe="/")
        pointer = (
            f"{REFERENCE}\n# Reused capture reference\n\n"
            "This file is a pointer, not capture substance or a fresh source review.\n\n"
            f"[Open the full reviewed capture]({reference}). Read it and its linked coverage/exception records before analysis. "
            "Relative source and supplement links belong to that canonical capture's folder.\n"
        )
        _atomic(output, pointer.encode("utf-8"))
        return source
    copied = {**record, "capture": output.name,
              "source": os.path.relpath((source.parent / record["source"]).resolve(), output.parent.resolve())}
    _write(metadata_path(output), {**copied, "reviewed": False})
    _atomic(output, content)
    _write(metadata_path(output), copied)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__ + " Native image workflow; video uses analyze_video.py.")
    parser.add_argument("action", choices=("lookup", "register", "accept"))
    parser.add_argument("media", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--model", required=True, help="Actual host/model identity used for native image capture")
    parser.add_argument("--prompt", type=Path, default=IMAGE_PROMPT)
    parser.add_argument("--reuse-root", type=Path)
    parser.add_argument("--review-note", default="")
    args = parser.parse_args()
    try:
        capture_contract = contract("image", "image", args.model, args.prompt.read_text(encoding="utf-8"))
        protected = (args.prompt,)
        if args.action == "lookup":
            match = lookup(args.media, args.capture, capture_contract, args.reuse_root, protected)
            if match is None:
                parser.exit(1, "No reviewed matching capture.\n")
            path, record = match
            print(json.dumps({"capture_path": str(path.resolve()), **record}, ensure_ascii=False))
        elif args.action == "register":
            register(args.media, args.capture, capture_contract, protected)
            print(f"Pending review: {args.capture}")
        else:
            accept(args.media, args.capture, capture_contract, args.review_note, protected)
            print(f"Reviewed for reuse: {args.capture}")
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.exit(2, f"Cannot use capture: {error}\n")


if __name__ == "__main__":
    main()
