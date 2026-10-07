import { request } from "./client";
import { type Keeper, token } from "./token";
import type { SessionInfo } from "./types";

type Fetch = (path: string, init?: RequestInit) => Promise<Response>;

/** What an address at /open signs the page in with. */
export type Secret = { code: string } | { token: string };

/** The secret an address at /open carries: its code if it has one, which is the launch's, and
 * its token otherwise, which is the printed address, pasted. */
export function secretOf(pathname: string, search: string): Secret | null {
  if (pathname !== "/open") return null;
  const query = new URLSearchParams(search);
  const code = query.get("code");
  if (code) return { code };
  const token = query.get("token");
  if (token) return { token };
  return null;
}

/** Where the page lands once signed in: the open project's page, or the start page, as the
 * page `/open` answered with before part 18b refreshed to. */
export function landingOf(session: SessionInfo): "/project" | "/" {
  return session.project === null ? "/" : "/project";
}

function isTokenReply(body: unknown): body is { token: string } {
  return (
    typeof body === "object" && body !== null && "token" in body && typeof body.token === "string"
  );
}

/** Sign the page in from its own address, before it asks the server anything else.
 *
 * An address at /open loses its secret the moment it is read, before the secret is sent
 * anywhere, so that it stays in no history. The secret is posted to /open, and the token
 * answered is kept. A refusal clears any token kept: the page then asks as it is, is answered
 * 401, and says it is signed out. */
export async function signInFrom(
  address: { pathname: string; search: string },
  replace: (path: string) => void,
  kept: Keeper = token,
  fetchImpl: Fetch = fetch,
): Promise<void> {
  if (address.pathname !== "/open") return;
  const secret = secretOf(address.pathname, address.search);
  replace("/");
  if (secret === null) return;
  let response: Response;
  try {
    response = await fetchImpl("/open", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(secret),
    });
  } catch {
    // Not answering: the page's first ask says so.
    return;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || !isTokenReply(body)) {
    kept.clear();
    return;
  }
  kept.set(body.token);
  try {
    replace(landingOf(await request<SessionInfo>("/api/session", {}, fetchImpl, kept)));
  } catch {
    // The page's own first ask meets the same failure, and says so.
  }
}
