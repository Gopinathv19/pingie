"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";
import { loginWithGoogle } from "../actions";

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

interface GoogleId {
  accounts: {
    id: {
      initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
      renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
    };
  };
}

export function GoogleButton() {
  const slot = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onCredential = useCallback(async ({ credential }: { credential: string }) => {
    setError(null);
    setBusy(true);
    const result = await loginWithGoogle(credential);
    if (result?.error) {
      setError(result.error);
      setBusy(false);
    }
  }, []);

  const init = useCallback(() => {
    const google = (window as unknown as { google?: GoogleId }).google;
    if (!CLIENT_ID || !google || !slot.current) return;
    google.accounts.id.initialize({ client_id: CLIENT_ID, callback: onCredential });
    google.accounts.id.renderButton(slot.current, {
      theme: "filled_black",
      size: "large",
      shape: "rectangular",
      text: "continue_with",
      width: 296,
    });
  }, [onCredential]);

  // The GSI script may already be cached, in which case onReady does not fire.
  useEffect(() => init(), [init]);

  if (!CLIENT_ID) {
    return <p className="error">NEXT_PUBLIC_GOOGLE_CLIENT_ID is not set in ping-admin/.env</p>;
  }

  return (
    <>
      <Script src="https://accounts.google.com/gsi/client" onReady={init} />
      <div ref={slot} aria-busy={busy} style={{ minHeight: 44, opacity: busy ? 0.5 : 1 }} />
      {busy && <p className="muted" style={{ fontSize: 12 }}>Signing in…</p>}
      {error && <p className="error">{error}</p>}
    </>
  );
}
