import { GoogleButton } from "./GoogleButton";
import s from "./login.module.css";

export const metadata = { title: "Login" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ expired?: string }> }) {
  const { expired } = await searchParams;
  return (
    <div className={s.page}>
      <div className={s.card}>
        <div className={s.logo}>Pingie Admin</div>
        <h1 className={s.title}>Sign in</h1>
        <p className="muted" style={{ fontSize: 13, marginBottom: 20 }}>
          Use your Google account. Only approved admin emails can sign in.
        </p>
        {expired && <p className="error" style={{ marginBottom: 12 }}>Your session expired. Sign in again.</p>}
        <div className={s.form}>
          <GoogleButton />
        </div>
      </div>
    </div>
  );
}
