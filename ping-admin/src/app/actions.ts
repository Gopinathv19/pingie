"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AdminApiError, EMAIL_COOKIE, SESSION_COOKIE, adminApi } from "@/lib/api";

const COOKIE_OPTS = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  maxAge: 60 * 60 * 8,
  path: "/",
};

export async function loginWithGoogle(credential: string): Promise<{ error: string } | undefined> {
  let session: { token: string; email: string };
  try {
    session = await adminApi.googleLogin(credential);
  } catch (e) {
    return { error: e instanceof AdminApiError ? e.message : "Sign-in failed" };
  }
  const jar = await cookies();
  jar.set(SESSION_COOKIE, session.token, COOKIE_OPTS);
  jar.set(EMAIL_COOKIE, session.email, COOKIE_OPTS);
  redirect("/orgs");
}

export async function logout() {
  const jar = await cookies();
  jar.delete(SESSION_COOKIE);
  jar.delete(EMAIL_COOKIE);
  redirect("/login");
}
