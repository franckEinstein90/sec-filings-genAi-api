"""Turn EDGAR HTML/text or uploaded PDFs into plain text."""

from __future__ import annotations

import io
import re

from bs4 import BeautifulSoup
from pypdf import PdfReader

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SPACES = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")


def extract_text(payload: bytes, filename: str | None = None, content_type: str | None = None) -> str:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if name.endswith(".pdf") or "pdf" in ctype:
        return extract_pdf(payload)
    if name.endswith(".htm") or name.endswith(".html") or "html" in ctype or _looks_like_html(payload):
        return extract_html(payload)
    return _normalize(payload.decode("utf-8", errors="ignore"))


def extract_pdf(payload: bytes) -> str:
    reader = PdfReader(io.BytesIO(payload))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"[Page {index}]\n{text}")
    return _normalize("\n\n".join(pages))


def extract_html(payload: bytes) -> str:
    soup = BeautifulSoup(payload, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return _normalize(text)


def _looks_like_html(payload: bytes) -> bool:
    head = payload[:400].lower()
    return b"<html" in head or b"<!doctype html" in head or b"<document>" in head


def _normalize(text: str) -> str:
    text = _CONTROL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    text = _BLANK.sub("\n\n", text)
    return text.strip()
