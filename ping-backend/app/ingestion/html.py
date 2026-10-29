"""HTML -> markdown for crawled pages.

Memora reads HTML as raw text with the tags left in, so Ping cleans pages
itself and pushes markdown: navigation, footers, scripts and cookie banners
removed, headings kept as `#` so Memora's chunker can follow the structure.
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

_DROP = (
    "script", "style", "noscript", "template", "svg", "canvas", "iframe",
    "nav", "header", "footer", "aside", "form", "button", "select", "input",
)
_NOISE = re.compile(r"(cookie|consent|banner|newsletter|sidebar|breadcrumb|share|social|related|advert|popup|modal)", re.I)
_BLOCK = {"p", "div", "section", "article", "main", "blockquote", "pre", "figure", "figcaption", "dl", "dd", "dt"}
_STRUCTURAL = list(_BLOCK | {"h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "br"})


@dataclass
class Page:
    title: str
    markdown: str

    @property
    def word_count(self) -> int:
        return len(self.markdown.split())


def html_to_markdown(html: str, fallback_title: str = "") -> Page:
    soup = BeautifulSoup(html, "html.parser")
    title = _title(soup) or fallback_title

    for tag in soup.find_all(_DROP):
        tag.decompose()
    for tag in soup.find_all(True):
        if tag.decomposed:
            continue
        marker = " ".join(tag.get("class") or []) + " " + (tag.get("id") or "")
        if tag.name not in ("body", "main", "article") and _NOISE.search(marker):
            tag.decompose()
        elif tag.get("aria-hidden") == "true" or tag.get("hidden") is not None:
            tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
    lines: list[str] = []
    _walk(root, lines)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if title and not text.startswith("# "):
        text = f"# {title}\n\n{text}"
    return Page(title=title, markdown=text)


def _title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(" ", strip=True) if h1 else ""


def _inline(tag: Tag) -> str:
    text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
    # get_text(" ") puts a space before punctuation that followed a tag.
    return re.sub(r" ([.,;:!?)])", r"\1", text)


def _walk(node: Tag, lines: list[str]) -> None:
    for child in node.children:
        if isinstance(child, NavigableString):
            text = re.sub(r"\s+", " ", str(child)).strip()
            if text:
                lines.append(text)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _inline(child)
            if text:
                lines.extend(["", "#" * int(name[1]) + " " + text, ""])
        elif name in ("ul", "ol"):
            for i, li in enumerate(child.find_all("li", recursive=False), start=1):
                text = _inline(li)
                if text:
                    lines.append(f"{i}. {text}" if name == "ol" else f"- {text}")
            lines.append("")
        elif name == "table":
            for row in child.find_all("tr"):
                cells = [_inline(c) for c in row.find_all(["th", "td"])]
                if any(cells):
                    lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
        elif name == "br":
            lines.append("")
        elif name in _BLOCK:
            if not child.find(_STRUCTURAL):
                # Only inline content: one line, so "<b>Settings</b>" stays
                # inside its sentence.
                text = _inline(child)
                if text:
                    lines.extend([text, ""])
                continue
            before = len(lines)
            _walk(child, lines)
            if len(lines) > before:
                lines.append("")
        else:
            _walk(child, lines)
