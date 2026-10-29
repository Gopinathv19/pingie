import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { EMAIL_COOKIE, SESSION_COOKIE } from "@/lib/api";
import { logout } from "./actions";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Pingie Admin", template: "%s · Pingie Admin" },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const jar = await cookies();
  const signedIn = Boolean(jar.get(SESSION_COOKIE)?.value);
  const email = jar.get(EMAIL_COOKIE)?.value;

  return (
    <html lang="en">
      <body>
        {signedIn && (
          <header className="topbar">
            <span className="brand">Pingie Admin</span>
            <nav className="nav">
              <Link href="/orgs">Organizations</Link>
              <Link href="/plans">Plans</Link>
            </nav>
            <div className="who">
              {email && <span className="muted">{email}</span>}
              <form action={logout}>
                <button type="submit" className="btn">Log out</button>
              </form>
            </div>
          </header>
        )}
        {children}
      </body>
    </html>
  );
}
