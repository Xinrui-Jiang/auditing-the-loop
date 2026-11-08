"""Evidence tools (PLAN.md §7 M3): ffprobe, cut and freeze detection, ASR. Deterministic; no prompts.
Each tool answers the checklist items it covers (B6, B4, A1) with a RawVerdict and an Observation."""
from __future__ import annotations

import json
import os
import re
import string
import subprocess
from pathlib import Path

import jiwer
from pydantic import BaseModel

from .schemas import Checklist, Observation, RawVerdict, Status

ASR_MODEL = "mlx-community/whisper-small-mlx"
WER_PASS, WER_FAIL = 0.25, 0.5  # one word off in a four-word line still passes; half wrong fails
SCENE_THRESHOLD = 0.4
FREEZE_NOISE, FREEZE_MIN_S, FREEZE_FAIL_S = 0.003, 0.5, 1.0
_PUNCT = str.maketrans("", "", string.punctuation + "“”‘’—–…")


class MediaInfo(BaseModel):
    duration_s: float
    width: int
    height: int
    fps: float
    has_audio: bool


class Word(BaseModel):
    word: str
    start: float
    end: float


class Transcript(BaseModel):
    text: str
    language: str
    words: list[Word]


def _ffmpeg_log(args: list[str]) -> str:
    proc = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", *args, "-f", "null", "-"], capture_output=True, text=True)
    return proc.stderr


def ffprobe(video: Path) -> MediaInfo:
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    num, _, den = video_stream["avg_frame_rate"].partition("/")
    return MediaInfo(duration_s=float(data["format"]["duration"]), width=video_stream["width"], height=video_stream["height"],
                     fps=round(float(num) / float(den), 3), has_audio=any(s["codec_type"] == "audio" for s in data["streams"]))


def scene_cuts(video: Path) -> list[float]:
    log = _ffmpeg_log(["-i", str(video), "-vf", f"select='gt(scene,{SCENE_THRESHOLD})',showinfo", "-an"])
    return [round(float(t), 2) for t in re.findall(r"Parsed_showinfo.*?pts_time:\s*([0-9.]+)", log)]


def freezes(video: Path) -> list[tuple[float, float]]:
    log = _ffmpeg_log(["-i", str(video), "-vf", f"freezedetect=n={FREEZE_NOISE}:d={FREEZE_MIN_S}", "-an"])
    starts = [float(x) for x in re.findall(r"freeze_start:\s*([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(r"freeze_end:\s*([0-9.]+)", log)]
    return [(round(s, 2), round(e, 2)) for s, e in zip(starts, ends)]


def transcribe(video: Path, model: str = ASR_MODEL) -> Transcript:
    """No initial prompt is given to whisper, so the transcript is independent of the scripted line."""
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    import mlx_whisper  # heavy import, kept local

    result = mlx_whisper.transcribe(str(video), path_or_hf_repo=model, word_timestamps=True, temperature=0.0,
                                    condition_on_previous_text=False, verbose=None)
    words = [Word(word=w["word"].strip(), start=round(float(w["start"]), 2), end=round(float(w["end"]), 2))
             for seg in result["segments"] for w in seg["words"]]
    return Transcript(text=result["text"].strip(), language=result["language"], words=words)


def normalise_speech(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("-", " ").translate(_PUNCT)).strip()


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref, hyp = normalise_speech(reference), normalise_speech(hypothesis)
    if not hyp:
        return 1.0
    return float(jiwer.wer(ref, hyp))


def dialogue_status(language: str, wer: float, expected_language: str) -> Status:
    if language != expected_language or wer >= WER_FAIL:
        return "fail"
    if wer <= WER_PASS:
        return "pass"
    return "uncertain"


def tool_verdicts(video: Path, checklist: Checklist, expected_duration_s: int, expected_short_side: int) -> tuple[list[RawVerdict], list[Observation]]:
    """Answer the B6, B4 and A1 items of the checklist from tools. Items the checklist lacks are skipped."""
    verdicts: list[RawVerdict] = []
    observations: list[Observation] = []
    info = ffprobe(video)
    by_check = {i.check_id: i for i in checklist.items}
    if "B6" in by_check:
        short_side = min(info.width, info.height)  # providers round 480p to 480-496 px
        ok = (abs(info.duration_s - expected_duration_s) <= 0.6 and abs(short_side - expected_short_side) <= 0.1 * expected_short_side
              and info.height > info.width and info.has_audio)
        text = f"{info.width}x{info.height}, {info.duration_s:.2f} s, {info.fps} fps, audio={'yes' if info.has_audio else 'no'}"
        verdicts.append(RawVerdict(item_id=by_check["B6"].id, source="tool/ffprobe", status="pass" if ok else "fail",
                                   visibility="seen_clearly", evidence=text))
        observations.append(Observation(source="tool/ffprobe", model_id="ffprobe", request_id=None, cost_usd=0.0, text=text, raw_path=None))
    if "B4" in by_check:
        cuts, frozen = scene_cuts(video), freezes(video)
        frozen_s = sum(e - s for s, e in frozen)
        text = f"scene cuts at {cuts}; frozen spans {frozen} ({frozen_s:.1f} s)"
        status: Status = "fail" if cuts or frozen_s >= FREEZE_FAIL_S else "pass"
        span = (cuts[0], cuts[0]) if cuts else (frozen[0] if frozen else None)
        verdicts.append(RawVerdict(item_id=by_check["B4"].id, source="tool/ffmpeg", status=status, visibility="seen_clearly", evidence=text, span=span))
        observations.append(Observation(source="tool/ffmpeg", model_id="ffmpeg scene+freezedetect", request_id=None, cost_usd=0.0, text=text, raw_path=None))
    if "A1" in by_check and info.has_audio:
        item = by_check["A1"]
        transcript = transcribe(video)
        wer = word_error_rate(item.params.line, transcript.text)
        status = dialogue_status(transcript.language, wer, item.params.language)
        text = f"language={transcript.language}, WER={wer:.2f}, heard: {transcript.text!r}"
        span = (transcript.words[0].start, transcript.words[-1].end) if transcript.words else None
        verdicts.append(RawVerdict(item_id=item.id, source="tool/asr", status=status, visibility="seen_clearly", evidence=text, span=span, value=round(wer, 3)))
        observations.append(Observation(source="tool/asr", model_id=ASR_MODEL, request_id=None, cost_usd=0.0, text=transcript.model_dump_json(), raw_path=None))
    elif "A1" in by_check:
        verdicts.append(RawVerdict(item_id=by_check["A1"].id, source="tool/asr", status="fail", visibility="seen_clearly", evidence="no audio stream"))
    return verdicts, observations
