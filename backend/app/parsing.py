"""Parse speaker-labeled transcript PDFs into speaker turns and chunks.

Transcript format: "Speaker Name: text ..." paragraphs with inline [HH:MM:SS]
timestamp markers roughly once per minute.
"""

import re
from dataclasses import dataclass, field

import fitz  # pymupdf

TIMESTAMP_RE = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]")
# Speaker labels: 1-4 capitalized words followed by a colon at line start
SPEAKER_RE = re.compile(r"^([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3}):\s*(.*)$")


@dataclass
class Turn:
    speaker: str
    text: str
    page: int          # 1-indexed page where the turn starts
    timestamp: str     # last [HH:MM:SS] marker seen at or before this turn


@dataclass
class Chunk:
    chunk_id: str
    source: str        # transcript display name
    text: str          # "Speaker: text" lines joined
    speakers: list[str]
    ts_start: str
    ts_end: str
    page_start: int
    page_end: int
    index: int = field(default=0)


def parse_pdf_bytes(data: bytes) -> list[Turn]:
    """Detect speaker-labeled transcript turns ("Speaker: text" lines, with
    inline [HH:MM:SS] markers) from an in-memory PDF. Returns [] if the PDF
    doesn't look like a speaker-labeled transcript - callers should fall back
    to chunk_plain_pages() in that case."""
    doc = fitz.open(stream=data, filetype="pdf")
    turns: list[Turn] = []
    current_ts = "00:00:00"
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            ts_matches = TIMESTAMP_RE.findall(line)
            m = SPEAKER_RE.match(line)
            if m and len(m.group(1)) <= 40:
                speaker, rest = m.group(1), m.group(2)
                rest = TIMESTAMP_RE.sub("", rest).strip()
                turns.append(Turn(speaker=speaker, text=rest, page=page_num, timestamp=current_ts))
            else:
                cleaned = TIMESTAMP_RE.sub("", line).strip()
                if cleaned and turns:
                    turns[-1].text = (turns[-1].text + " " + cleaned).strip()
            if ts_matches:
                current_ts = ts_matches[-1]
    doc.close()
    return [t for t in turns if t.text]


def chunk_plain_pages(data: bytes, source_name: str, target_chars: int = 1500) -> list[Chunk]:
    """Fallback chunker for uploaded PDFs that aren't speaker-labeled transcripts:
    chunk by page text directly, no speaker/timestamp metadata available."""
    doc = fitz.open(stream=data, filetype="pdf")
    chunks: list[Chunk] = []
    buf = ""
    buf_start_page = 1
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if not text:
            continue
        buf = (buf + "\n" + text).strip() if buf else text
        if len(buf) >= target_chars:
            idx = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{source_name}::chunk-{idx}",
                    source=source_name,
                    text=buf,
                    speakers=[],
                    ts_start="",
                    ts_end="",
                    page_start=buf_start_page,
                    page_end=page_num,
                    index=idx,
                )
            )
            buf = ""
            buf_start_page = page_num + 1
    if buf:
        idx = len(chunks)
        chunks.append(
            Chunk(
                chunk_id=f"{source_name}::chunk-{idx}",
                source=source_name,
                text=buf,
                speakers=[],
                ts_start="",
                ts_end="",
                page_start=buf_start_page,
                page_end=len(doc),
                index=idx,
            )
        )
    doc.close()
    return chunks


def chunk_turns(
    turns: list[Turn],
    source_name: str,
    target_chars: int = 1500,
    overlap_turns: int = 2,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[Turn] = []
    buf_chars = 0
    i = 0

    def flush(buffer: list[Turn]) -> None:
        if not buffer:
            return
        idx = len(chunks)
        text = "\n".join(f"{t.speaker}: {t.text}" for t in buffer)
        speakers = sorted({t.speaker for t in buffer})
        chunks.append(
            Chunk(
                chunk_id=f"{source_name}::chunk-{idx}",
                source=source_name,
                text=text,
                speakers=speakers,
                ts_start=buffer[0].timestamp,
                ts_end=buffer[-1].timestamp,
                page_start=buffer[0].page,
                page_end=buffer[-1].page,
                index=idx,
            )
        )

    while i < len(turns):
        t = turns[i]
        buf.append(t)
        buf_chars += len(t.text)
        if buf_chars >= target_chars:
            flush(buf)
            # start next chunk with a small overlap for context continuity
            buf = buf[-overlap_turns:] if overlap_turns else []
            buf_chars = sum(len(x.text) for x in buf)
        i += 1
    # flush remainder if it holds anything beyond the overlap carryover
    if buf and sum(len(x.text) for x in buf) > 200:
        flush(buf)
    return chunks
