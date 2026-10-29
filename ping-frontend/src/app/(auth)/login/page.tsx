"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";
import { InlineError } from "@/components/ui/States";
import { ApiError, api } from "@/lib/api";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

interface GoogleId {
  accounts: {
    id: {
      initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
      renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
    };
  };
}

// Only same-site paths, so a crafted ?next= can't send people off-site.
function nextPath() {
  const next = new URLSearchParams(window.location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/bots";
}

// Google is the only way in. The first sign-in creates the account and its
// workspace.
export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const slot = useRef<HTMLDivElement>(null);

  const onCredential = useCallback(async (response: { credential: string }) => {
    setError(null);
    setBusy(true);
    try {
      await api.auth.google(response.credential);
      // Full navigation: the shell reads the session once on mount.
      window.location.href = nextPath();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Google sign-in failed");
      setBusy(false);
    }
  }, []);

  const initGoogle = useCallback(() => {
    const google = (window as unknown as { google?: GoogleId }).google;
    if (!GOOGLE_CLIENT_ID || !google || !slot.current) return;
    google.accounts.id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: onCredential });
    google.accounts.id.renderButton(slot.current, {
      theme: "filled_black",
      size: "large",
      shape: "rectangular",
      text: "continue_with",
      width: 316,
    });
  }, [onCredential]);

  // The script may already be cached, in which case onReady does not fire.
  useEffect(() => {
    initGoogle();
  }, [initGoogle]);

  // Already signed in? Go straight to the dashboard.
  useEffect(() => {
    api.auth.me().then(
      () => (window.location.href = nextPath()),
      () => undefined,
    );
  }, []);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        backgroundImage: "radial-gradient(var(--dot) 1px, transparent 1px)",
        backgroundSize: "18px 18px",
      }}
    >
      {GOOGLE_CLIENT_ID && <Script src="https://accounts.google.com/gsi/client" onReady={initGoogle} />}

      <div style={{ width: "100%", maxWidth: 380, display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 700 }}>
          <span
            style={{
              width: 28,
              height: 28,
              background: "var(--accent-strong)",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
            }}
          >
            P
          </span>
          Pingie
        </div>

        <div className="panel">
          <div className="panel-header" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
            <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em" }}>Sign in</h1>
            <span className="muted" style={{ fontSize: 13 }}>
              Use your Google account. The first sign-in creates your workspace.
            </span>
          </div>
          <div className="panel-body" style={{ alignItems: "center" }}>
            {GOOGLE_CLIENT_ID ? (
              <div
                ref={slot}
                aria-busy={busy}
                style={{ minHeight: 44, opacity: busy ? 0.5 : 1, pointerEvents: busy ? "none" : undefined }}
              />
            ) : (
              <InlineError message="Google sign-in is not configured. Set NEXT_PUBLIC_GOOGLE_CLIENT_ID in ping-frontend/.env.local and restart the dev server." />
            )}
            {busy && (
              <span className="muted" style={{ fontSize: 13 }}>
                Signing in…
              </span>
            )}
            <div style={{ width: "100%" }}>
              <InlineError message={error} />
            </div>
          </div>
        </div>

        <p className="subtle" style={{ margin: 0, fontSize: 12, textAlign: "center" }}>
          By continuing you agree to the Terms and Privacy Policy.
        </p>
      </div>
    </div>
  );
}
