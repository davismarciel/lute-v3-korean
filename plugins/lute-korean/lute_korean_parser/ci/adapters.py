"""Deterministic text/subtitle adapters; translations and cue IDs stay metadata."""
import csv
import re
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from .models import CandidateContent, CandidateSegment

TIME = r"(?:\d{1,3}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"
DURATION = r"(?:\d+(?:\.\d+)?h\s*)?(?:\d+(?:\.\d+)?m\s*)?(?:\d+(?:\.\d+)?s)?"
CUE = re.compile(rf"^\s*({TIME})\s*-->\s*({TIME})(?:\s+.*)?$")
TIMED_LINE = re.compile(rf"^\s*\[?({TIME})\]?\s+(.*)$")
SPEAKER = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _-]{0,30}|[가-힣]{1,8}):\s+(.*)$", re.S)


def seconds(value):
    """Parse a technical timestamp, never a lexical token."""
    if ":" not in value:
        units = {"h": 3600, "m": 60, "s": 1}
        return sum(
            float(number) * units[unit]
            for number, unit in re.findall(r"(\d+(?:\.\d+)?)([hms])", value)
        )
    parts = value.replace(",", ".").split(":")
    return sum(float(part) * 60**index for index, part in enumerate(reversed(parts)))


class _TextCleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"br", "div", "p"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"div", "p"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_segment(text):
    """Only presentation markup; Korean morphology is handled exclusively by Kiwi."""
    raw = text
    text = re.sub(r"\[sound:[^\]]+\]", "", text, flags=re.I)
    text = re.sub(r"<\d{1,3}:\d{2}(?::\d{2})?[.,]\d{3}>", "", text)
    cleaner = _TextCleaner()
    cleaner.feed(text)
    text = "".join(cleaner.parts).strip()
    metadata = {}
    match = SPEAKER.match(text)
    if match:
        metadata["speaker"] = match[1]
        text = match[2].strip()
    if text != raw.strip():
        metadata["original_text"] = raw
    if re.search(r"\[sound:", raw, re.I):
        metadata["has_audio_markup"] = True
    return text, metadata


def _segment(index, identity, text, timestamp=None, end=None, metadata=None):
    cleaned, extra = clean_segment(text)
    return CandidateSegment(
        index,
        str(identity),
        cleaned,
        timestamp,
        seconds(timestamp) if timestamp else None,
        seconds(end) if end else None,
        dict(metadata or {}, **extra),
    )


class PlainTextAdapter:
    """Lines and sentence punctuation provide deterministic analysis segments."""

    def segments(self, text):
        result = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            for sentence_number, sentence in enumerate(
                re.split(r"(?<=[.!?。！？])\s+", line.strip()), 1
            ):
                if sentence.strip():
                    result.append(
                        _segment(
                            len(result),
                            f"line:{line_number}:sentence:{sentence_number}",
                            sentence,
                            metadata={"source_line": line_number},
                        )
                    )
        return tuple(result)


class TimestampTranscriptAdapter:
    """Only unmistakable leading timestamps are separated from subtitle text."""

    def segments(self, text):
        result = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            match = TIMED_LINE.match(line)
            result.append(
                _segment(
                    len(result),
                    f"line:{number}",
                    match[2] if match else line,
                    timestamp=match[1] if match else None,
                    metadata={"source_line": number},
                )
            )
        return tuple(result)


def tprs_header(lines):
    """Only the exact three-column header identifies a table; titles stay metadata."""
    for index, line in enumerate(lines[:5]):
        delimiter = "\t" if "\t" in line else "|"
        header = [
            h.strip().casefold() for h in next(csv.reader([line], delimiter=delimiter))
        ]
        if {"time", "subtitle", "machine translation"} <= set(header):
            return index, delimiter, header
    return None


class TPRSTranscriptAdapter:
    """Require exact explicit header columns, never guess translated content."""

    def segments(self, text):
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return ()
        found = tprs_header(lines)
        if found is None:
            raise ValueError(
                "TPRS requires Time, Subtitle, Machine Translation headers"
            )
        header_index, delimiter, headers = found
        title = "\n".join(lines[:header_index])
        rows = list(csv.reader(lines[header_index:], delimiter=delimiter))
        positions = {
            name: headers.index(name)
            for name in ("time", "subtitle", "machine translation")
        }
        result = []
        for number, row in enumerate(rows[1:], header_index + 2):
            if row and all(
                re.fullmatch(r":?-+:?", value.strip()) for value in row if value.strip()
            ):
                continue
            if len(row) != len(headers):
                raise ValueError(f"Ambiguous TPRS row {number}")
            stamp = row[positions["time"]].strip()
            if stamp and not re.fullmatch(rf"(?:{TIME}|{DURATION})", stamp):
                raise ValueError(f"Invalid TPRS timestamp on row {number}")
            result.append(
                _segment(
                    len(result),
                    f"tprs:{number}",
                    row[positions["subtitle"]].strip(),
                    timestamp=stamp or None,
                    metadata={
                        "translation": row[positions["machine translation"]].strip(),
                        "source_line": number,
                        "transcript_title": title,
                    },
                )
            )
        return tuple(result)


class SRTAdapter:
    """Keep cue identity/time; reject malformed cues rather than silently losing text."""

    def segments(self, text):
        result = []
        for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
            lines = block.splitlines()
            if not lines:
                continue
            timing = next(
                (i for i, line in enumerate(lines[:2]) if CUE.match(line)), None
            )
            if timing is None:
                raise ValueError(
                    "Invalid subtitle cue; plain fallback preserves content"
                )
            match = CUE.match(lines[timing])
            identity = lines[0] if timing else str(len(result) + 1)
            if seconds(match[2]) < seconds(match[1]):
                raise ValueError("Subtitle end precedes start")
            result.append(
                _segment(
                    len(result),
                    identity,
                    "\n".join(lines[timing + 1 :]),
                    match[1],
                    match[2],
                )
            )
        return tuple(result)


class VTTAdapter(SRTAdapter):
    """VTT headers, NOTE, STYLE, REGION blocks and cue settings are technical."""

    def segments(self, text):
        blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
        cues = [
            b for b in blocks if not b.startswith(("WEBVTT", "NOTE", "STYLE", "REGION"))
        ]
        return super().segments("\n\n".join(cues))


ADAPTERS = {
    "plain": PlainTextAdapter,
    "timestamp": TimestampTranscriptAdapter,
    "tprs": TPRSTranscriptAdapter,
    "srt": SRTAdapter,
    "vtt": VTTAdapter,
}


def adapt_content(text, name="candidate", format="auto", kind="text"):
    """Auto detection fails conservatively to plain with an explicit warning."""
    if not isinstance(text, str):
        raise ValueError("Content must be Unicode text")
    if kind not in {"text", "podcast", "dialogue", "tprs", "subtitle"}:
        raise ValueError("Invalid content kind")
    original = text
    text = text.lstrip("\ufeff")
    warnings = []
    if format == "auto":
        first = next((line for line in text.splitlines() if line.strip()), "")
        extension = Path(name).suffix.lower()
        if tprs_header([line for line in text.splitlines() if line.strip()]):
            format = "tprs"
        elif text.startswith("WEBVTT") or extension == ".vtt":
            format = "vtt"
        elif extension == ".srt" or any(CUE.match(line) for line in text.splitlines()):
            format = "srt"
        elif "|" in first or "\t" in first:
            format = "plain"
            warnings.append(
                "Ambiguous table: plain text fallback; translations could be present"
            )
        elif any(TIMED_LINE.match(line) for line in text.splitlines()):
            format = "timestamp"
        else:
            format = "plain"
    if format not in ADAPTERS:
        raise ValueError("Unsupported content format")
    try:
        segments = ADAPTERS[format]().segments(text)
    except ValueError as exc:
        warnings.append(str(exc))
        format = "plain"
        segments = PlainTextAdapter().segments(text)
    return CandidateContent(
        name,
        format,
        segments,
        sha256(original.encode()).hexdigest(),
        kind,
        tuple(warnings),
    )
