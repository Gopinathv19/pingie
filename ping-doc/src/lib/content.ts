import fs from "node:fs";
import path from "node:path";
import { Marked, type Tokens } from "marked";
import { FLAT_NAV } from "./nav";

const CONTENT = path.join(process.cwd(), "content");

export interface Heading {
  id: string;
  text: string;
  depth: number;
}

export interface Doc {
  href: string;
  title: string;
  description: string;
  html: string;
  headings: Heading[];
  text: string;
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/<[^>]+>/g, "")
    .replace(/&[a-z]+;/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function parseFrontmatter(raw: string): { data: Record<string, string>; body: string } {
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return { data: {}, body: raw };
  const data: Record<string, string> = {};
  for (const line of m[1].split("\n")) {
    const i = line.indexOf(":");
    if (i > 0) data[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^"(.*)"$/, "$1");
  }
  return { data, body: raw.slice(m[0].length) };
}

function render(body: string): { html: string; headings: Heading[] } {
  const headings: Heading[] = [];
  const used = new Map<string, number>();
  const marked = new Marked({ gfm: true });
  marked.use({
    renderer: {
      heading(this: { parser: { parseInline: (t: Tokens.Heading["tokens"]) => string } }, token: Tokens.Heading) {
        const inner = this.parser.parseInline(token.tokens);
        let id = slugify(token.text);
        const n = used.get(id) ?? 0;
        used.set(id, n + 1);
        if (n) id = `${id}-${n}`;
        if (token.depth === 2 || token.depth === 3) headings.push({ id, text: token.text.replace(/`/g, ""), depth: token.depth });
        return `<h${token.depth} id="${id}"><a class="anchor" href="#${id}" aria-hidden="true">#</a>${inner}</h${token.depth}>\n`;
      },
      code(token: Tokens.Code) {
        const lang = (token.lang || "").split(/\s/)[0];
        const label = lang ? `<span class="code-lang">${escapeHtml(lang)}</span>` : "";
        return `<div class="code">${label}<pre><code class="language-${escapeHtml(lang || "text")}">${escapeHtml(token.text)}</code></pre></div>\n`;
      },
      blockquote(this: { parser: { parse: (t: Tokens.Blockquote["tokens"]) => string } }, token: Tokens.Blockquote) {
        const inner = this.parser.parse(token.tokens);
        const kind = /^<p><strong>(Note|Tip|Warning|Important)<\/strong>/i.exec(inner)?.[1]?.toLowerCase() ?? "note";
        return `<div class="callout callout-${kind}">${inner}</div>\n`;
      },
      table(this: unknown, token: Tokens.Table) {
        const cell = (c: Tokens.TableCell) => (this as { parser: { parseInline: (t: Tokens.TableCell["tokens"]) => string } }).parser.parseInline(c.tokens);
        const head = token.header.map((c) => `<th>${cell(c)}</th>`).join("");
        const rows = token.rows.map((r) => `<tr>${r.map((c) => `<td>${cell(c)}</td>`).join("")}</tr>`).join("");
        return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>\n`;
      },
    },
  });
  return { html: marked.parse(body, { async: false }) as string, headings };
}

function fileFor(href: string): string {
  const slug = href === "/" ? "index" : href.replace(/^\//, "");
  return path.join(CONTENT, `${slug}.md`);
}

export function guideHrefs(): string[] {
  return FLAT_NAV.map((n) => n.href).filter((h) => !h.startsWith("/api-reference") && fs.existsSync(fileFor(h)));
}

export function getDoc(href: string): Doc | null {
  const file = fileFor(href);
  if (!fs.existsSync(file)) return null;
  const { data, body } = parseFrontmatter(fs.readFileSync(file, "utf8"));
  const { html, headings } = render(body);
  const text = body
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[#>*_`|[\]()-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return { href, title: data.title ?? href, description: data.description ?? "", html, headings, text };
}
