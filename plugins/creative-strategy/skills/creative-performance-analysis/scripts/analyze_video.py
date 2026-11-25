#!/usr/bin/env python3
"""
Capture a video via Gemini in quick or detailed mode.

Quick captures visual events, speech and readable text. Detailed uses the
original spatial/audio analysis prompt. Prompts live beside this skill.

Usage:
    analyze_video.py <video-path> [output-path] [--mode quick|detailed]

If output-path is omitted, defaults to:
    <video-dir>/Analyses/<video-filename>.<mode>.md

Needs only the Python standard library. The Gemini key comes from GEMINI_API_KEY or
~/.config/creative-strategy/.env; when neither has one, the script creates that file,
opens it in a text editor and says where to get a key. No credentials are printed.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROMPT_PATH = SCRIPT_DIR / "prompts" / "full.md"
QUICK_PROMPT_PATH = SCRIPT_DIR / "prompts" / "quick.md"
DEFAULT_MODEL = "gemini-flash-latest"
sys.path.insert(0, str(SCRIPT_DIR))
import media_capture
sys.path.pop(0)

# This is the "Ad Substance Summary" deliverable that gets appended to the
# detailed system instruction. Prompted structure is not proof of fidelity.
SUBSTANCE_DELIVERABLE = """
After completing all required structured sections, ALSO append a final \
"## Ad Substance Summary" section containing:
- Full verbatim spoken transcript (numbered by speaker turn if multiple speakers, with timestamps)
- All on-screen text in chronological order with timestamps
- Observable presentation (talking head, demonstration, motion graphics, etc.); do not infer who produced it
- Length and apparent aspect ratio
- Hook: exact first 3 seconds described (visual + audio + on-screen text)
- Body: how the middle 70% builds
- Close: how it ends, including any CTA wording
- Any badges/stickers/offers superimposed
- The single most distinctive creative element
"""

SYSTEM_INSTRUCTION_PREAMBLE = """You are a meticulous video analyst. Your \
ENTIRE output must follow the structured analysis methodology below. \
Begin with the \
<mandatory_audio_verification> three passes and produce all three declarations \
verbatim. Then complete <temporal_visibility_tracking> with the full \
visibility log declaration. Then proceed through every numbered phase. Do not \
summarize prematurely or skip to conclusions. The caller requires the full \
structured analysis. Report any unavailable evidence or incomplete coverage \
honestly. Never claim a check passed merely because its declaration is \
requested; mark that check incomplete instead.
"""


KEY_URL = "https://aistudio.google.com/apikey"
ENV_FILE = Path.home() / ".config" / "creative-strategy" / ".env"
ENV_TEMPLATE = (
    "# Your Gemini API key, used only for video analysis.\n"
    f"# Get a free key at {KEY_URL}, paste it after the = sign below, then save this file.\n"
    "GEMINI_API_KEY=\n"
)
API = "https://generativelanguage.googleapis.com"


def read_env_file(path: Path, name: str) -> str:
    """Return one KEY=value entry from a .env file, or an empty string."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            return value.strip().strip("'\"").strip()
    return ""


def open_in_editor(path: Path) -> bool:
    """Open a file in the user's text editor without waiting; report whether a launcher ran."""
    if sys.platform == "darwin":
        command = ["open", "-t", str(path)]
    elif sys.platform.startswith("win"):
        command = ["notepad", str(path)]
    else:
        command = ["xdg-open", str(path)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def resolve_gemini_api_key() -> str:
    """Return the user's key, or create the key file, open it and stop with instructions."""
    if key := os.environ.get("GEMINI_API_KEY", "").strip():
        return key
    if key := read_env_file(ENV_FILE, "GEMINI_API_KEY"):
        return key
    if not ENV_FILE.exists():
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(ENV_TEMPLATE, encoding="utf-8")
        try:
            ENV_FILE.chmod(0o600)
        except OSError:
            pass
    opened = open_in_editor(ENV_FILE)
    where = f"I opened {ENV_FILE} in your text editor." if opened else f"Open {ENV_FILE} in a text editor."
    raise SystemExit(f"NEEDS_GEMINI_KEY: {where} Get a free key at {KEY_URL}, paste it after "
                     "GEMINI_API_KEY=, save the file, then run this again.")


def gemini_error(error: Exception) -> SystemExit:
    """Turn a failed Gemini call into a plain message that never contains the key."""
    if isinstance(error, urllib.error.HTTPError):
        try:
            detail = json.loads(error.read().decode("utf-8")).get("error", {})
        except (OSError, ValueError, AttributeError):
            detail = {}
        message = str(detail.get("message", ""))
        if error.code in (400, 401, 403) and ("API key" in message or "API_KEY" in json.dumps(detail)):
            return SystemExit(f"GEMINI_KEY_REJECTED: Gemini rejected your API key. Paste a fresh key from {KEY_URL} "
                              f"into {ENV_FILE}, save the file, then run this again.")
        if error.code == 503:
            return SystemExit("GEMINI_BUSY: Gemini is busy right now. Try again in a few minutes.")
        return SystemExit(f"Gemini request failed ({error.code}): {message or error.reason}")
    reason = getattr(error, "reason", error)
    if "CERTIFICATE_VERIFY_FAILED" in str(reason):
        return SystemExit("This Python cannot verify secure connections. On macOS with Python from python.org, "
                          "run 'Install Certificates.command' in the Python folder under Applications, then try again.")
    return SystemExit(f"Could not reach Gemini: {reason}")


class Client:
    """The few Gemini calls this script makes, over HTTPS with the standard library."""

    def __init__(self, api_key: str):
        self.files = SimpleNamespace(upload=self._upload, get=self._get, delete=self._delete)
        self.models = SimpleNamespace(generate_content=self._generate)
        self._key = api_key

    def _call(self, method: str, url: str, body: bytes | None = None, headers: dict | None = None):
        request = urllib.request.Request(url, data=body, method=method,
                                         headers={"x-goog-api-key": self._key, **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                text = response.read().decode("utf-8")
                return response.headers, (json.loads(text) if text.strip() else {})
        except (urllib.error.URLError, OSError) as error:
            raise gemini_error(error) from None

    @staticmethod
    def _file(data: dict) -> SimpleNamespace:
        data = data.get("file", data)
        return SimpleNamespace(name=data["name"], uri=data.get("uri"),
                               mime_type=data.get("mimeType"), state=data.get("state", ""))

    def _upload(self, file: str) -> SimpleNamespace:
        path = Path(file)
        mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
        content = path.read_bytes()
        headers, _ = self._call("POST", f"{API}/upload/v1beta/files",
                                json.dumps({"file": {"display_name": path.name}}).encode("utf-8"),
                                {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                                 "X-Goog-Upload-Header-Content-Length": str(len(content)),
                                 "X-Goog-Upload-Header-Content-Type": mime, "Content-Type": "application/json"})
        upload_url = headers.get("X-Goog-Upload-URL")
        if not upload_url:
            raise SystemExit("Gemini did not return an upload address.")
        _, data = self._call("POST", upload_url, content,
                             {"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize",
                              "Content-Length": str(len(content))})
        return self._file(data)

    def _get(self, name: str) -> SimpleNamespace:
        return self._file(self._call("GET", f"{API}/v1beta/{name}")[1])

    def check(self) -> None:
        """Make the cheapest authenticated call, so a bad key fails here."""
        self._call("GET", f"{API}/v1beta/models?pageSize=1")

    def _delete(self, name: str) -> None:
        self._call("DELETE", f"{API}/v1beta/{name}")

    def _generate(self, model: str, contents: list, config: dict) -> SimpleNamespace:
        text_part, upload = contents
        body = {
            "system_instruction": {"parts": [{"text": config["system_instruction"]}]},
            "contents": [{"role": "user", "parts": [
                {"text": text_part}, {"file_data": {"mime_type": upload.mime_type, "file_uri": upload.uri}}]}],
        }
        _, data = self._call("POST", f"{API}/v1beta/models/{model}:generateContent",
                             json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
        return SimpleNamespace(text="".join(part.get("text", "") for part in parts),
                               candidates=[SimpleNamespace(finish_reason=c.get("finishReason")) for c in candidates])


def wait_for_active(client, upload, timeout_s: int = 240):
    """Poll an uploaded file until it's ACTIVE or FAILED."""
    started = time.monotonic()
    while True:
        if time.monotonic() - started > timeout_s:
            raise SystemExit(f"Gemini upload timeout (>{timeout_s}s)")
        current = client.files.get(name=upload.name)
        state = str(getattr(current, "state", "")).upper()
        if "ACTIVE" in state:
            return current
        if "FAILED" in state:
            raise SystemExit("Gemini upload state = FAILED")
        time.sleep(2)


def analyze(
    video_path: Path,
    output_path: Path,
    prompt_path: Path,
    model: str,
    plain_prompt: bool = False,
    mode: str = "quick",
    refresh: bool = False,
    reuse_root: Path | None = None,
    accept_review: str | None = None,
    register_capture: bool = False,
) -> Path:
    if not video_path.is_file():
        raise SystemExit(f"Video not found: {video_path}")
    if not prompt_path.is_file():
        raise SystemExit(f"Prompt file not found: {prompt_path}")
    try:
        media_capture.protect(video_path, output_path, (prompt_path,))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if mode not in ("quick", "detailed"):
        raise SystemExit(f"Unknown capture mode: {mode}")
    video_prompt = prompt_path.read_text(encoding="utf-8")
    if not video_prompt.strip():
        raise SystemExit("Prompt is empty.")
    initial_media_hash = media_capture.sha(video_path)

    if plain_prompt or mode == "quick":
        system_instruction = video_prompt
        user_msg = "Analyze the attached video and return exactly the requested output."
    else:
        system_instruction = SYSTEM_INSTRUCTION_PREAMBLE + "\n" + video_prompt + SUBSTANCE_DELIVERABLE
        user_msg = "Analyze the attached video using the detailed instructions."
    capture_mode = "custom" if plain_prompt else mode
    capture_contract = media_capture.contract(
        "video", capture_mode, model, json.dumps([system_instruction, user_msg], ensure_ascii=False)
    )
    if register_capture:
        if accept_review is not None:
            raise ValueError("Register a pending capture before accepting its review.")
        try:
            existing = json.loads(media_capture.metadata_path(output_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict) and (existing.get("contract") != capture_contract
                                           or existing.get("media_sha256") != media_capture.sha(video_path)):
            raise ValueError("This capture's record names a different video or capture settings (mode, model or prompt); "
                             "register it only with those, or capture again.")
        media_capture.register(video_path, output_path, capture_contract, (prompt_path,))
        print(f"Pending review: {output_path}", flush=True)
        return output_path
    if accept_review is not None:
        media_capture.accept(video_path, output_path, capture_contract, accept_review, (prompt_path,))
        print(f"Reviewed for reuse: {output_path}", flush=True)
        return output_path
    if not refresh:
        match = media_capture.lookup(video_path, output_path, capture_contract, reuse_root, (prompt_path,))
        if match is not None:
            path, record = match
            canonical = media_capture.materialize(video_path, output_path, match, (prompt_path,))
            print(f"[{video_path.name}] REUSED — {canonical}; requested output: {output_path}; reviewed source: {record['source']} (record at {path})", flush=True)
            return canonical

    client = Client(resolve_gemini_api_key())
    upload = None
    try:
        print(f"[{video_path.name}] Uploading to Gemini...", flush=True)
        upload = client.files.upload(file=str(video_path))
        upload = wait_for_active(client, upload)

        print(f"[{video_path.name}] Generating analysis (model={model})...", flush=True)
        response = client.models.generate_content(
            model=model,
            contents=[user_msg, upload],
            config={"system_instruction": system_instruction},
        )
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise SystemExit("Gemini returned no capture text; previous output was preserved.")
        for candidate in getattr(response, "candidates", None) or []:
            reason = getattr(candidate, "finish_reason", None)
            if reason and str(getattr(reason, "name", reason)).split(".")[-1] != "STOP":
                raise SystemExit(
                    "Gemini did not finish normally; previous output was preserved."
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if media_capture.sha(video_path) != initial_media_hash:
            raise SystemExit("Source video changed during capture; previous output was preserved. Run again with the settled source.")
        content = (
            f"# Analysis: {video_path.name}\n\n"
            f"Capture mode: {capture_mode}; model: {model}. "
            f"Model output; not independently verified.\n\n{text}\n"
        )
        temporary_output = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=output_path.parent,
                prefix=".capture-", suffix=".tmp", delete=False,
            ) as handle:
                temporary_output = Path(handle.name)
                handle.write(content)
            # Invalidate an earlier approval before replacement, even if the text is identical.
            media_capture.register(video_path, output_path, capture_contract, (prompt_path,), content.encode("utf-8"))
            os.replace(temporary_output, output_path)
        finally:
            if temporary_output is not None:
                temporary_output.unlink(missing_ok=True)
        print(
            f"[{video_path.name}] DONE — {len(text):,} chars written to {output_path}",
            flush=True,
        )
        return output_path
    finally:
        if upload is not None:
            try:
                client.files.delete(name=upload.name)
            except (Exception, SystemExit):
                pass


def setup() -> None:
    """Check everything video work needs, creating and opening the key file when the key is missing."""
    if sys.version_info < (3, 11):
        raise SystemExit(f"Python 3.11 or later is needed; this is {sys.version.split()[0]}.")
    Client(resolve_gemini_api_key()).check()
    print("Gemini key works.")
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        print("ffmpeg and ffprobe found.")
    else:
        print("ffmpeg not found. Only the footage similarity check needs it; install it with "
              "'brew install ffmpeg' (macOS) or 'winget install ffmpeg' (Windows).")
    print("Video analysis is ready.")


def default_output_path(video_path: Path, mode: str = "quick") -> Path:
    """Keep input extension and mode so distinct captures cannot collide."""
    return video_path.parent / "Analyses" / f"{video_path.name}.{mode}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, nargs="?", help="Path to the video file")
    parser.add_argument("--setup", action="store_true",
                        help="Check the Gemini key (opening the key file if it's missing) and ffmpeg; no upload")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output md path (default: <video-dir>/Analyses/<filename>.<mode>.md)",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Override the selected mode's prompt file",
    )
    parser.add_argument("--mode", choices=("quick", "detailed"), default="quick")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model id (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--plain-prompt",
        action="store_true",
        help="Use the supplied prompt directly as the system instruction without ad-specific defaults",
    )
    parser.add_argument("--refresh", action="store_true", help="Recapture despite a reviewed match when source inspection shows a limitation")
    parser.add_argument("--reuse-root", type=Path, help="Also search this folder, which must contain the video, for reviewed captures of identical bytes")
    review_actions = parser.add_mutually_exclusive_group()
    review_actions.add_argument("--register-capture", action="store_true", help="Bind an existing or corrected full capture to its known source and capture settings as pending; no API call")
    review_actions.add_argument("--accept-review", metavar="NOTE", help="After source/coverage checks, accept the existing pending capture for reuse; no API call")
    args = parser.parse_args()
    if args.setup:
        setup()
        return
    if args.video is None:
        parser.error("give a video path, or --setup")

    video = args.video.expanduser().resolve()
    output = (
        args.output or default_output_path(video, "custom" if args.plain_prompt else args.mode)
    ).expanduser().resolve()
    prompt = (
        args.prompt or (QUICK_PROMPT_PATH if args.mode == "quick" else DEFAULT_PROMPT_PATH)
    ).expanduser().resolve()

    try:
        analyze(video, output, prompt, args.model, args.plain_prompt, args.mode,
                refresh=args.refresh, reuse_root=args.reuse_root, accept_review=args.accept_review,
                register_capture=args.register_capture)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot capture video: {error}\n")


if __name__ == "__main__":
    main()
