import spec from "@/data/openapi.json";

export type Schema = {
  $ref?: string;
  type?: string;
  format?: string;
  title?: string;
  description?: string;
  enum?: (string | number)[];
  const?: string | number;
  items?: Schema;
  properties?: Record<string, Schema>;
  required?: string[];
  anyOf?: Schema[];
  allOf?: Schema[];
  oneOf?: Schema[];
  additionalProperties?: Schema | boolean;
  default?: unknown;
  maxLength?: number;
  minLength?: number;
  minimum?: number;
  maximum?: number;
  pattern?: string;
};

export interface Parameter {
  name: string;
  in: "path" | "query" | "header" | "cookie";
  required?: boolean;
  description?: string;
  schema?: Schema;
}

export interface Operation {
  method: string;
  path: string;
  tag: string;
  summary: string;
  description: string;
  operationId: string;
  parameters: Parameter[];
  body?: { contentType: string; schema: Schema; required: boolean };
  responses: { status: string; description: string; schema?: Schema; contentType?: string }[];
}

type RawOp = {
  tags?: string[];
  summary?: string;
  description?: string;
  operationId: string;
  parameters?: Parameter[];
  requestBody?: { required?: boolean; content: Record<string, { schema: Schema }> };
  responses: Record<string, { description: string; content?: Record<string, { schema: Schema }> }>;
};

const raw = spec as unknown as {
  paths: Record<string, Record<string, RawOp>>;
  components: { schemas: Record<string, Schema> };
};

export type Auth = "session" | "widget" | "widget-start" | "admin" | "none";

export interface TagInfo {
  key: string;
  title: string;
  description: string;
  auth: Auth;
  internal?: boolean;
}

/** Display order, names and auth for each OpenAPI tag. */
export const TAGS: TagInfo[] = [
  { key: "widget", title: "Widget (public)", auth: "widget", description: "What the embedded widget calls from your website: config, conversations, streamed answers, feedback, identify, and live-chat handoff. Authorised by the page's Origin and a per-conversation token, never a user session." },
  { key: "auth", title: "Authentication", auth: "session", description: "Google sign-in for the dashboard and the session cookie it sets." },
  { key: "organizations", title: "Workspaces", auth: "session", description: "Workspaces (organizations) you belong to, their usage, and creating bots in them." },
  { key: "bots", title: "Bots", auth: "session", description: "Read and change a bot, its appearance, analytics overview and install snippet." },
  { key: "knowledge", title: "Knowledge", auth: "session", description: "Sources a bot answers from: file uploads, URLs and sitemaps, re-sync, and the retrieval tester." },
  { key: "answers", title: "Team answers", auth: "session", description: "Answers your team teaches the bot from unanswered questions." },
  { key: "domains", title: "Allowed domains", auth: "session", description: "Hostnames where a bot's widget may load." },
  { key: "conversations", title: "Conversations & live chat", auth: "session", description: "The inbox, transcripts, CSV export, leads, and live-chat actions: take over, reply, hand back, close." },
  { key: "live", title: "Agent presence", auth: "session", description: "Mark yourself available for live chat and list chats waiting for a person." },
  { key: "sharing", title: "Members, sharing & invitations", auth: "session", description: "Workspace members, sharing single bots, and accepting or declining invitations." },
  { key: "plans", title: "Plans", auth: "none", description: "The public plan catalogue shown on the pricing page." },
  { key: "meta", title: "Health", auth: "none", description: "Liveness check." },
  { key: "admin", title: "Admin (internal)", auth: "admin", internal: true, description: "Used by the ping-admin console only. Requires an admin token issued to an allow-listed Google account." },
];

export const AUTH_TEXT: Record<Auth, string> = {
  session: "Dashboard session: the ping_session cookie from Google sign-in, or the same JWT as Authorization: Bearer.",
  widget: "Widget: the Origin header must be on the bot's allowed domains, plus X-Conversation-Token for conversation routes.",
  "widget-start": "Widget: the Origin header must be on the bot's allowed domains.",
  admin: "Admin: Authorization: Bearer <admin token> from POST /admin/auth/google.",
  none: "None: public.",
};

const METHODS = ["get", "post", "put", "patch", "delete"];

function title(op: RawOp, method: string, path: string): string {
  return op.summary || `${method.toUpperCase()} ${path}`;
}

export function allOperations(): Operation[] {
  const ops: Operation[] = [];
  for (const [path, item] of Object.entries(raw.paths)) {
    for (const method of METHODS) {
      const op = item[method];
      if (!op) continue;
      const bodyEntry = op.requestBody ? Object.entries(op.requestBody.content)[0] : undefined;
      ops.push({
        method,
        path,
        tag: op.tags?.[0] ?? "meta",
        summary: title(op, method, path),
        description: op.description ?? "",
        operationId: op.operationId,
        parameters: op.parameters ?? [],
        body: bodyEntry ? { contentType: bodyEntry[0], schema: bodyEntry[1].schema, required: !!op.requestBody?.required } : undefined,
        responses: Object.entries(op.responses)
          .filter(([status]) => status !== "422")
          .map(([status, r]) => {
            const c = r.content ? Object.entries(r.content)[0] : undefined;
            return { status, description: r.description, schema: c?.[1].schema, contentType: c?.[0] };
          }),
      });
    }
  }
  return ops;
}

export function operationsFor(tag: string): Operation[] {
  return allOperations().filter((o) => o.tag === tag);
}

export function opAnchor(op: Operation): string {
  return `${op.method}-${op.path}`.replace(/[{}]/g, "").replace(/[^a-zA-Z0-9]+/g, "-").replace(/-+$/, "").toLowerCase();
}

export function authFor(op: Operation, tag: TagInfo): Auth {
  if (op.path.endsWith("/admin/auth/google")) return "none";
  if (tag.key === "widget") return /\/conversations\/\{conversation_id\}/.test(op.path) ? "widget" : "widget-start";
  if (op.path === "/api/v1/auth/google") return "none";
  if (op.path === "/api/v1/invitations/by-token/{token}" && op.method === "get") return "none";
  return tag.auth;
}

export function resolve(s: Schema | undefined): Schema | undefined {
  if (!s) return s;
  if (s.$ref) return raw.components.schemas[s.$ref.split("/").pop()!];
  return s;
}

export function refName(s: Schema | undefined): string | null {
  return s?.$ref ? s.$ref.split("/").pop()! : null;
}

/** Drop `null` from anyOf so optional fields read as their real type. */
export function nonNull(s: Schema): { schema: Schema; nullable: boolean } {
  if (s.anyOf) {
    const rest = s.anyOf.filter((x) => x.type !== "null");
    if (rest.length === 1) return { schema: { ...rest[0], description: s.description ?? rest[0].description, default: s.default }, nullable: rest.length !== s.anyOf.length };
  }
  return { schema: s, nullable: false };
}

export function typeLabel(s: Schema | undefined): string {
  if (!s) return "any";
  const name = refName(s);
  if (name) return name;
  const { schema, nullable } = nonNull(s);
  if (schema !== s) return typeLabel(schema) + (nullable ? " | null" : "");
  if (s.anyOf || s.oneOf) return (s.anyOf ?? s.oneOf)!.map(typeLabel).join(" | ");
  if (s.enum) return s.enum.map((v) => JSON.stringify(v)).join(" | ");
  if (s.const !== undefined) return JSON.stringify(s.const);
  if (s.type === "array") return `${typeLabel(s.items)}[]`;
  if (s.type === "object" && !s.properties) return "object";
  return s.format ? `${s.type} (${s.format})` : s.type ?? "any";
}

export function counts() {
  const ops = allOperations();
  return { operations: ops.length, byTag: Object.fromEntries(TAGS.map((t) => [t.key, ops.filter((o) => o.tag === t.key).length])) };
}
