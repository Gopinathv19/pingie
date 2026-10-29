"use client";

export function Loading({ label = "Loading…", height = 160 }: { label?: string; height?: number }) {
  return (
    <div className="empty" style={{ minHeight: height, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <span className="spinner" aria-hidden="true" />
      <span style={{ marginLeft: 10 }}>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function InlineError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="error-box" role="alert">
      {message}
    </div>
  );
}
