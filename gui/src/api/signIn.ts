import { type Fetch, request } from "./client";
import { type Keeper, token } from "./token";
import type { SessionInfo } from "./types";

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
 * anywhere: the tab's history entry is replaced, never pushed, so that the secret stays in no
 * history. The secret is posted to /open, and the token answered is kept.
 *
 * A POST that got no answer at all - the fetch itself rejecting, as it did when Windows refused
 * Chromium a socket (net::ERR_NO_BUFFER_SPACE, WSAENOBUFS, in CI run 37710529902) - is sent once
 * more, at once: without it, the page went on with no token and told the reader to open the very
 * address they had just opened. An answered POST never is. The second try costs this much: a
 * launch code whose first POST reached the server, and only its answer was lost, is spent
 * already, so the second is refused 403 and the terminal prints its warning of a code presented
 * again - a false alarm, the reader signed out as they would have been without the second try.
 * The token, pasted, is no single-use secret, and is answered again.
 *
 * Any other answer, a refusal or the connection cap's 503 among them, leaves a token already
 * kept as it was. Cleared, it would let any page sign the reader out of every tab, by sending
 * this one to /open with a wrong code; a stale token is cleared by the first 401 it meets
 * anyway (ruling P18b-6). With none kept, the page then asks as it is, is answered 401, and
 * says it is signed out. */
export async function signInFrom(
  address: { pathname: string; search: string },
  history: Pick<History, "replaceState">,
  kept: Keeper = token,
  fetchImpl: Fetch = fetch,
): Promise<void> {
  if (address.pathname !== "/open") return;
  const secret = secretOf(address.pathname, address.search);
  history.replaceState(null, "", "/");
  if (secret === null) return;
  const post = () =>
    fetchImpl("/open", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(secret),
    });
  let response: Response;
  try {
    // Once more only where the first got no answer at all: `catch` sees a rejected fetch, never
    // an HTTP answer, whatever its status.
    response = await post().catch(post);
  } catch {
    // Not answering, twice: the page's first ask says so.
    return;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || !isTokenReply(body)) return;
  kept.set(body.token);
  try {
    const session = await request<SessionInfo>("/api/session", {}, fetchImpl, kept);
    history.replaceState(null, "", landingOf(session));
  } catch {
    // The page's own first ask meets the same failure, and says so.
  }
}
