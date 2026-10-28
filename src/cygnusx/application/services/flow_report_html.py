"""Read BioReport's offline gzip editions without executing its original loader."""

from __future__ import annotations

import base64
import gzip
import io
from html.parser import HTMLParser


class _Editions(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.current: str | None = None
        self.parts: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type") == "application/octet-stream":
            edition = attributes.get("id", "")
            if edition in {"edition-zh", "edition-en"}:
                if edition in self.parts:
                    raise ValueError("Duplicate BioReport edition")
                self.current = edition
                self.parts[edition] = []

    def handle_data(self, data: str) -> None:
        if self.current:
            self.parts[self.current].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.current = None


def report_editions(content: bytes, maximum: int) -> dict[str, bytes]:
    """Bound both the archive and each decoded document, including gzip bombs."""
    if not content or len(content) > maximum:
        raise ValueError("Report HTML exceeds import preview budget")
    text = content.decode("utf-8")
    if 'id="edition-zh"' not in text and "id='edition-zh'" not in text:
        return {"zh": content}
    parser = _Editions()
    parser.feed(text)
    if set(parser.parts) != {"edition-zh", "edition-en"}:
        raise ValueError("Incomplete BioReport editions")
    result: dict[str, bytes] = {}
    for name, parts in parser.parts.items():
        compressed = base64.b64decode("".join("".join(parts).split()), validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            decoded = stream.read(maximum + 1)
        if not decoded or len(decoded) > maximum:
            raise ValueError("Decoded BioReport edition exceeds preview budget")
        decoded.decode("utf-8")
        result[name.removeprefix("edition-")] = decoded
    return result
