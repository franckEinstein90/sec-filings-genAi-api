"""Section-aware chunking for 10-K / 10-Q style documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sec_filings.config import CHUNK_OVERLAP, CHUNK_SIZE

ITEM_HEADING = re.compile(
    r"(?im)^(?:item\s+)(\d{1,2}[a-z]?)(?:\s*[.\-–:]\s*|\s+)(.{0,80})$"
)


@dataclass(frozen=True)
class TextChunk:
    content: str
    section: str | None
    chunk_index: int


def chunk_filing_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    sections = _split_sections(text)
    chunks: list[TextChunk] = []
    index = 0
    for section_name, section_text in sections:
        for piece in split_text(section_text, chunk_size, chunk_overlap):
            if not piece.strip():
                continue
            chunks.append(TextChunk(content=piece.strip(), section=section_name, chunk_index=index))
            index += 1
    return chunks


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separators = ["\n\n", "\n", ". ", " ", ""]
    return _split_recursive(text, chunk_size, chunk_overlap, separators)


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    matches = list(ITEM_HEADING.finditer(text))
    if not matches:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("Preamble", preamble))

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        heading = f"Item {match.group(1).upper()}"
        title = match.group(2).strip(" .-–:")
        if title:
            heading = f"{heading} {title[:60]}"
        body = text[match.start() : end].strip()
        if body:
            sections.append((heading, body))
    return sections


def _split_recursive(text: str, chunk_size: int, overlap: int, separators: list[str]) -> list[str]:
    separator = separators[0]
    rest = separators[1:]
    if separator:
        parts = text.split(separator)
    else:
        parts = list(text)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else (current + separator + part if separator else current + part)
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(part) > chunk_size:
            if rest:
                chunks.extend(_split_recursive(part, chunk_size, overlap, rest))
                current = ""
            else:
                chunks.extend(_window(part, chunk_size, overlap))
                current = ""
        else:
            current = part
    if current:
        chunks.append(current)
    return _apply_overlap(chunks, overlap)


def _window(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(chunk_size - overlap, 1)
    return [text[i : i + chunk_size] for i in range(0, len(text), step)]


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    overlapped = [chunks[0]]
    for chunk in chunks[1:]:
        previous = overlapped[-1]
        prefix = previous[-overlap:] if len(previous) > overlap else previous
        if not chunk.startswith(prefix):
            overlapped.append((prefix + " " + chunk).strip())
        else:
            overlapped.append(chunk)
    return overlapped
