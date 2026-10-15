"""Extract the ministry-authored press text from one reviewed KOGL Type 1 page.

The caller supplies previously fetched HTML. Attachments, photos, navigation,
and third-party material outside the press-text container are never stored.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re

from .provider_registry import Provider, MOTIR_PRESS_DOCUMENT, permits_document_storage
from .source_share import SourceShareError

MAX_HTML_BYTES = 256 * 1024


class _PressTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sequence_ids: list[str] = []
        self.blocks: list[str] = []
        self.depth = 0
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "input" and values.get("name") == "bbsSeqN":
            self.sequence_ids.append(values.get("value") or "")
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif {"detail-cont", "mViewerContents"}.issubset(
                (values.get("class") or "").split()
            ):
                self.depth = 1
                self.parts = []
        if self.depth:
            if tag in {"script", "style"}:
                self.skip += 1
            if tag in {"p", "br", "tr", "li"}:
                self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self.depth:
            return
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        if tag in {"p", "br", "tr", "li"}:
            self.parts.append("\n")
        if tag == "div":
            self.depth -= 1
            if not self.depth:
                self.blocks.append("".join(self.parts))

    def handle_data(self, data: str) -> None:
        if self.depth and not self.skip:
            self.parts.append(data)


def extract_motir_press_text(provider: Provider, html: bytes) -> bytes:
    """Return UTF-8 body text; do not assert a source-backed relationship."""
    if not permits_document_storage(provider):
        raise SourceShareError("reviewed MOTIR public document permission required")
    match = MOTIR_PRESS_DOCUMENT.fullmatch(provider.endpoint)
    if match is None:
        raise SourceShareError("official MOTIR article URL required")
    if not isinstance(html, bytes) or not 0 < len(html) <= MAX_HTML_BYTES:
        raise SourceShareError("bounded official HTML required")
    try:
        source = html.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceShareError("official HTML must be UTF-8") from exc
    parser = _PressTextParser()
    parser.feed(source)
    parser.close()
    article_id = provider.endpoint.split("/")[-2]
    if parser.sequence_ids != [article_id] or len(parser.blocks) != 1:
        raise SourceShareError("article identity or press-text container mismatch")
    text = "\n".join(
        re.sub(r"\s+", " ", line).strip()
        for line in parser.blocks[0].splitlines()
    )
    text = "\n".join(line for line in text.splitlines() if line)
    payload = (text + "\n").encode("utf-8")
    if not 100 <= len(payload) <= 128 * 1024:
        raise SourceShareError("missing or unbounded press text")
    return payload
