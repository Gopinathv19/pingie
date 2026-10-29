import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const BACKEND = (process.env.BACKEND_URL ?? "http://localhost:8080").replace(/\/$/, "");
export const SESSION_COOKIE = "ping_admin_session";
export const EMAIL_COOKIE = "ping_admin_email";

export interface AdminOrg {
  id: string;
  name: string;
  slug: string;
  plan: string;
  plan_name: string;
  plan_paid: boolean;
  owner_email: string | null;
  owner_name: string | null;
  messages_used: number;
  messages_limit: number;
  bots_used: number;
  bots_limit: number;
  sources_limit: number;
  members_limit: number;
  shares_limit: number;
  remove_branding: boolean;
  stripe_customer_id: string | null;
  created_at: string;
  status: string;
}

export interface OrgPlanUpdate {
  plan: string;
  messages_limit?: number;
  bots_limit?: number;
  sources_limit?: number;
  members_limit?: number;
  shares_limit?: number;
  remove_branding?: boolean;
}

export type ModelTier = "fast" | "balanced" | "best";
export const MODEL_TIERS: ModelTier[] = ["fast", "balanced", "best"];

export interface PlanValues {
  name: string;
  description: string;
  price_monthly: number | null;
  price_label: string;
  messages_limit: number;
  bots_limit: number;
  sources_limit: number;
  members_limit: number;
  shares_limit: number;
  remove_branding: boolean;
  model_tiers: ModelTier[];
  features: string[];
  is_public: boolean;
  is_default: boolean;
  highlighted: boolean;
  sort_order: number;
  active: boolean;
}

export interface AdminPlan extends PlanValues {
  id: string;
  key: string;
  org_count: number;
  created_at: string;
  updated_at: string;
}

export class AdminApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit & { token?: string }): Promise<T> {
  const token = init?.token ?? (await cookies()).get(SESSION_COOKIE)?.value;
  const res = await fetch(`${BACKEND}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (res.status === 401 && !path.startsWith("/admin/auth")) redirect("/login?expired=1");
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new AdminApiError(body.detail ?? `HTTP ${res.status}`, res.status);
  }
  return res.json();
}

const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const adminApi = {
  googleLogin: (idToken: string) =>
    request<{ token: string; email: string }>("/admin/auth/google", { ...json("POST", { id_token: idToken }), token: "" }),

  listOrgs: (search?: string) =>
    request<AdminOrg[]>(`/admin/orgs${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  getOrg: (id: string) => request<AdminOrg>(`/admin/orgs/${id}`),
  updateOrgPlan: (id: string, payload: OrgPlanUpdate) => request<AdminOrg>(`/admin/orgs/${id}/plan`, json("PATCH", payload)),

  listPlans: () => request<AdminPlan[]>("/admin/plans"),
  getPlan: (key: string) => request<AdminPlan>(`/admin/plans/${encodeURIComponent(key)}`),
  createPlan: (payload: PlanValues & { key: string }) => request<AdminPlan>("/admin/plans", json("POST", payload)),
  updatePlan: (key: string, payload: Partial<PlanValues> & { apply_to_existing?: boolean }) =>
    request<AdminPlan>(`/admin/plans/${encodeURIComponent(key)}`, json("PATCH", payload)),
};
