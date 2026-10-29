// Typed client for ping-backend. Requests go to this app's own /api/v1, which
// next.config.ts forwards to the backend, so the session cookie is first-party.

import type {
  Bot,
  BotSummary,
  BotUpdate,
  ConversationDetail,
  ConversationFilter,
  ConversationSummary,
  ChatMessage,
  ConversationUpdates,
  LiveSummary,
  TeamAnswer,
  KnowledgeDraftItem,
  Domain,
  InstallInfo,
  Lead,
  InviteRole,
  Invitation,
  Org,
  PeopleList,
  Person,
  Plan,
  SharedBot,
  Overview,
  Source,
  SourceList,
  TestResult,
  TimeRange,
  User,
  WidgetAppearance,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(BASE + path, { ...init, headers, credentials: "same-origin" });
  } catch {
    throw new ApiError("Can't reach the server. Is ping-backend running?", 0, "network");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ")
          : response.status >= 500
            ? "The server could not complete the request."
            : `Request failed (${response.status})`;
    throw new ApiError(message, response.status, body?.code ?? "error");
  }
  return body as T;
}

const json = (method: string, data?: unknown): RequestInit => ({
  method,
  body: data === undefined ? undefined : JSON.stringify(data),
});

const qs = (params: Record<string, string | undefined>) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
  return s ? `?${s}` : "";
};

export const api = {
  auth: {
    google: (idToken: string) => request<{ user: User }>("/auth/google", json("POST", { id_token: idToken })),
    me: () => request<User>("/auth/me"),
    logout: () => request<void>("/auth/logout", json("POST")),
  },
  plans: {
    list: () => request<Plan[]>("/plans"),
  },
  members: {
    list: (orgId: string) =>
      request<{ members: Person[]; invitations: Invitation[]; seats_used: number; seats_limit: number }>(
        `/orgs/${orgId}/members`,
      ).then((r): PeopleList => ({ ...r, people: r.members })),
    invite: (orgId: string, email: string, role: InviteRole) =>
      request<Invitation>(`/orgs/${orgId}/invitations`, json("POST", { email, role })),
    resend: (orgId: string, invId: string) => request<Invitation>(`/orgs/${orgId}/invitations/${invId}/resend`, json("POST")),
    revoke: (orgId: string, invId: string) => request<void>(`/orgs/${orgId}/invitations/${invId}`, json("DELETE")),
    setRole: (orgId: string, userId: string, role: InviteRole) =>
      request<void>(`/orgs/${orgId}/members/${userId}`, json("PATCH", { role })),
    remove: (orgId: string, userId: string) => request<void>(`/orgs/${orgId}/members/${userId}`, json("DELETE")),
    leave: (orgId: string) => request<void>(`/orgs/${orgId}/members/me`, json("DELETE")),
  },
  shares: {
    list: (botId: string) =>
      request<{ shares: Person[]; invitations: Invitation[]; seats_used: number; seats_limit: number }>(
        `/bots/${botId}/shares`,
      ).then((r): PeopleList => ({ ...r, people: r.shares })),
    invite: (botId: string, email: string, role: InviteRole) =>
      request<Invitation>(`/bots/${botId}/invitations`, json("POST", { email, role })),
    resend: (botId: string, invId: string) => request<Invitation>(`/bots/${botId}/invitations/${invId}/resend`, json("POST")),
    revoke: (botId: string, invId: string) => request<void>(`/bots/${botId}/invitations/${invId}`, json("DELETE")),
    setRole: (botId: string, userId: string, role: InviteRole) =>
      request<void>(`/bots/${botId}/shares/${userId}`, json("PATCH", { role })),
    remove: (botId: string, userId: string) => request<void>(`/bots/${botId}/shares/${userId}`, json("DELETE")),
    sharedWithMe: () => request<SharedBot[]>("/shared-bots"),
    leave: (botId: string) => request<void>(`/shared-bots/${botId}`, json("DELETE")),
  },
  invitations: {
    mine: () => request<Invitation[]>("/invitations/mine"),
    accept: (id: string) => request<Invitation>(`/invitations/${id}/accept`, json("POST")),
    decline: (id: string) => request<Invitation>(`/invitations/${id}/decline`, json("POST")),
    preview: (token: string) => request<Invitation>(`/invitations/by-token/${encodeURIComponent(token)}`),
    acceptToken: (token: string) => request<Invitation>(`/invitations/by-token/${encodeURIComponent(token)}/accept`, json("POST")),
    declineToken: (token: string) => request<Invitation>(`/invitations/by-token/${encodeURIComponent(token)}/decline`, json("POST")),
  },
  orgs: {
    list: () => request<Org[]>("/orgs"),
    bots: (orgId: string) => request<BotSummary[]>(`/orgs/${orgId}/bots`),
    createBot: (orgId: string, data: { name: string; domain: string; sitemap_url?: string }) =>
      request<Bot>(`/orgs/${orgId}/bots`, json("POST", data)),
  },
  bots: {
    get: (id: string) => request<Bot>(`/bots/${id}`),
    update: (id: string, data: BotUpdate) => request<Bot>(`/bots/${id}`, json("PATCH", data)),
    remove: (id: string) => request<void>(`/bots/${id}`, json("DELETE")),
    overview: (id: string, range: TimeRange) => request<Overview>(`/bots/${id}/overview?range=${range}`),
    appearance: (id: string) => request<WidgetAppearance>(`/bots/${id}/appearance`),
    saveAppearance: (id: string, data: WidgetAppearance) =>
      request<WidgetAppearance>(`/bots/${id}/appearance`, json("PUT", data)),
    install: (id: string) => request<InstallInfo>(`/bots/${id}/install`),
  },
  conversations: {
    list: (botId: string, filter: ConversationFilter, q: string, before?: string) =>
      request<{ items: ConversationSummary[]; next_before: string | null }>(
        `/bots/${botId}/conversations${qs({ filter, q, before })}`,
      ),
    get: (botId: string, id: string) => request<ConversationDetail>(`/bots/${botId}/conversations/${id}`),
    clear: (botId: string) => request<void>(`/bots/${botId}/conversations`, json("DELETE")),
    exportUrl: (botId: string) => `${BASE}/bots/${botId}/conversations/export.csv`,
    leads: (botId: string) => request<Lead[]>(`/bots/${botId}/leads`),
    updates: (botId: string, id: string, after?: string) =>
      request<ConversationUpdates>(`/bots/${botId}/conversations/${id}/updates${qs({ after })}`),
    takeover: (botId: string, id: string) => request<void>(`/bots/${botId}/conversations/${id}/takeover`, json("POST")),
    reply: (botId: string, id: string, text: string) =>
      request<ChatMessage>(`/bots/${botId}/conversations/${id}/reply`, json("POST", { text })),
    handback: (botId: string, id: string) => request<void>(`/bots/${botId}/conversations/${id}/handback`, json("POST")),
    close: (botId: string, id: string) => request<void>(`/bots/${botId}/conversations/${id}/close`, json("POST")),
  },
  live: {
    presence: (available: boolean) => request<void>("/me/presence", json("POST", { available })),
    summary: () => request<LiveSummary>("/me/live"),
  },
  answers: {
    list: (botId: string) => request<TeamAnswer[]>(`/bots/${botId}/answers`),
    add: (
      botId: string,
      data: {
        question: string;
        answer: string;
        conversation_id?: string;
        also_reply?: boolean;
        kind?: "answer" | "summary" | "conversation";
        target_bot_ids?: string[];
      },
    ) => request<TeamAnswer>(`/bots/${botId}/answers`, json("POST", data)),
    draft: (botId: string, conversationId: string, mode: "summary" | "qa" | "transcript") =>
      request<{ items: KnowledgeDraftItem[] }>(
        `/bots/${botId}/answers/draft`,
        json("POST", { conversation_id: conversationId, mode }),
      ),
    update: (botId: string, id: string, data: { question: string; answer: string }) =>
      request<TeamAnswer>(`/bots/${botId}/answers/${id}`, json("PATCH", data)),
    remove: (botId: string, id: string) => request<void>(`/bots/${botId}/answers/${id}`, json("DELETE")),
  },
  sources: {
    list: (botId: string) => request<SourceList>(`/bots/${botId}/sources`),
    upload: (botId: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<Source>(`/bots/${botId}/sources/upload`, { method: "POST", body: form });
    },
    addUrl: (botId: string, url: string, kind: "url" | "sitemap") =>
      request<Source>(`/bots/${botId}/sources/url`, json("POST", { url, kind })),
    resync: (botId: string, id: string) => request<Source>(`/bots/${botId}/sources/${id}/resync`, json("POST")),
    remove: (botId: string, id: string) => request<void>(`/bots/${botId}/sources/${id}`, json("DELETE")),
    test: (botId: string, query: string, top_k: number, threshold: number) =>
      request<TestResult>(`/bots/${botId}/test`, json("POST", { query, top_k, threshold })),
  },
  domains: {
    list: (botId: string) => request<Domain[]>(`/bots/${botId}/domains`),
    add: (botId: string, host: string) => request<Domain>(`/bots/${botId}/domains`, json("POST", { host })),
    remove: (botId: string, id: string) => request<void>(`/bots/${botId}/domains/${id}`, json("DELETE")),
  },
};
