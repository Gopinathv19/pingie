"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Org, User } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { ErrorState, Loading } from "@/components/ui/States";

const ORG_KEY = "pingie-org";

interface Session {
  user: User;
  org: Org;
  orgs: Org[];
  isOwner: boolean;
  canEdit: boolean;
  switchOrg: (orgId: string) => void;
  reloadOrg: () => void;
}

const SessionContext = createContext<Session | null>(null);

/** Loads the signed-in user and their workspaces once for the whole shell.
 * The chosen workspace is remembered per browser. Without a session, useApi
 * sends the browser to /login. */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { data, error, reload } = useApi(async () => {
    const [user, orgs] = await Promise.all([api.auth.me(), api.orgs.list()]);
    return { user, orgs };
  }, []);
  const [orgId, setOrgId] = useState<string | null>(null);

  useEffect(() => {
    setOrgId(localStorage.getItem(ORG_KEY));
  }, []);

  const switchOrg = useCallback((id: string) => {
    localStorage.setItem(ORG_KEY, id);
    window.location.href = "/bots";
  }, []);

  if (error) {
    return (
      <div style={{ padding: 40 }}>
        <ErrorState message={error.message} onRetry={reload} />
      </div>
    );
  }
  if (!data) return <Loading label="Signing you in…" height={320} />;
  if (!data.orgs.length) {
    return (
      <div style={{ padding: 40 }}>
        <ErrorState message="Your account has no workspace." onRetry={reload} />
      </div>
    );
  }
  const org = data.orgs.find((o) => o.id === orgId) ?? data.orgs[0];
  return (
    <SessionContext.Provider
      value={{
        user: data.user,
        org,
        orgs: data.orgs,
        isOwner: org.role === "owner",
        canEdit: org.role !== "viewer",
        switchOrg,
        reloadOrg: reload,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}
