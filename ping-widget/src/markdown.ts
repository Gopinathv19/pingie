// A deliberately small Markdown renderer for bot replies. Everything is
// HTML-escaped first, so the only tags in the output are the ones added here.
// Supports paragraphs, line breaks, - / * / 1. lists, **bold**, *italic*,
// `code`, [text](https://...) links and bare https:// links. Help Center
// articles (`rich`) also get # headings and ![alt](https://...) images.

function escape(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function safeUrl(url: string): string | null {
  return /^(https?:\/\/|mailto:)/i.test(url) ? url : null;
}

function inline(text: string, rich = false): string {
  let out = escape(text);
  const links: string[] = [];
  const hold = (html: string) => `\u0000${links.push(html) - 1}\u0000`;

  out = out.replace(/`([^`]+)`/g, (_, code) => hold(`<code>${code}</code>`));
  out = out.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, alt, url) => {
    const src = url.replace(/&amp;/g, "&");
    // Images only in articles, and only over https; otherwise keep the alt text.
    return rich && /^https:\/\//i.test(src) ? hold(`<img src="${escape(src)}" alt="${alt}" loading="lazy">`) : alt;
  });
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, label, url) => {
    const href = safeUrl(url.replace(/&amp;/g, "&"));
    return href ? hold(`<a href="${escape(href)}" target="_blank" rel="noopener noreferrer">${label}</a>`) : m;
  });
  out = out.replace(/\bhttps?:\/\/[^\s<]+[^\s<.,;:!?)\]'"]/g, (url) =>
    hold(`<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`),
  );
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  return out.replace(/\u0000(\d+)\u0000/g, (_, i) => links[Number(i)]);
}

export function renderMarkdown(src: string, rich = false): string {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const html: string[] = [];
  let para: string[] = [];
  let list: { tag: "ul" | "ol"; items: string[] } | null = null;

  const flushPara = () => {
    if (para.length) html.push(`<p>${para.map((l) => inline(l, rich)).join("<br>")}</p>`);
    para = [];
  };
  const flushList = () => {
    if (list) html.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i, rich)}</li>`).join("")}</${list.tag}>`);
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const heading = rich ? /^(#{1,6})\s+(.*)$/.exec(line) : null;
    if (heading) {
      flushPara();
      flushList();
      const level = Math.min(heading[1].length + 1, 4); // the article title is the only h1
      html.push(`<h${level}>${inline(heading[2], rich)}</h${level}>`);
    } else if (bullet || numbered) {
      flushPara();
      const tag = bullet ? "ul" : "ol";
      if (!list || list.tag !== tag) {
        flushList();
        list = { tag, items: [] };
      }
      list.items.push((bullet || numbered)![1]);
    } else if (!line.trim()) {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line.replace(/^#{1,6}\s+/, ""));
    }
  }
  flushPara();
  flushList();
  return html.join("");
}
