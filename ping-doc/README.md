# ping-doc

The Pingie documentation site: guides for customers, how Pingie works, a full
REST API reference generated from ping-backend's OpenAPI schema, and internal
pages for the team. Next.js 16 + Markdown, statically generated.

## Run

```bash
npm install
npm run dev        # http://localhost:3003
```

## Write

- Pages are Markdown files in `content/` with a `title` and `description`
  front matter. `content/index.md` is the home page.
- The sidebar order lives in `src/lib/nav.ts`. A page appears once it's listed there.
- Callouts: start a blockquote with `**Note**`, `**Tip**`, `**Warning**` or `**Important**`.
- Raw HTML is allowed (e.g. the `cards` grid on the home page).

## API reference

`src/data/openapi.json` is a snapshot of the backend's schema. Regenerate it
whenever routes change (needs ping-backend's `.venv`):

```bash
npm run gen:api
```

Tag names, descriptions and auth labels are in `src/lib/openapi.ts` (`TAGS`).
A new backend tag must be added there to get its own page.

## Build

```bash
npm run build && npm run start
```
