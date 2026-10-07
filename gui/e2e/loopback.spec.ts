import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { expect, test } from "./fixtures";

/** What the other server's page asks that server for, beside the page itself: `/again`, at its
 * root as the page is, and `/api/session` and `/project`, under the paths of ddd gui's own API
 * and pages. A cookie scoped below `/` rides to its own path alone: `Path=/api`, which a download
 * link that cannot carry a header might reach for, would ride to `/api/session` and to neither
 * of the others. */
const ASKED = ["/again", "/api/session", "/project"];

// Part 18b's reason: a browser sends a cookie to every port of 127.0.0.1, and ddd gui's cookie
// was its token. Signed in through the printed address, the browser is taken to a server of
// its own on another port of the address, whose page then asks that server again, as any page
// landed on there may. That server records the target and every header line of every request,
// and the token is in none of them: no cookie carries it, and the page's own storage is out of
// this origin's reach.
test("another server on 127.0.0.1 is sent nothing of ddd gui's", async ({ page, gui }) => {
  const token = new URL(gui.address).searchParams.get("token");
  if (token === null) throw new Error(`ddd gui printed an address with no token: ${gui.address}`);
  await page.goto(gui.address);
  await page.waitForURL(/\/project$/);

  // The header lines as they came, not Node's `headers`, which drops a repeat of some lines,
  // `authorization` and `referer` among them.
  const seen: { url: string | undefined; raw: string[] }[] = [];
  const other = createServer((request, response) => {
    seen.push({ url: request.url, raw: request.rawHeaders });
    if (request.url === "/") {
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      response.end(
        `<!doctype html><title>other</title><script>Promise.allSettled(${JSON.stringify(ASKED)}` +
          '.map((path) => fetch(path, { credentials: "include" })))' +
          '.finally(() => { document.title = "asked"; });</script>',
      );
    } else {
      response.writeHead(204);
      response.end();
    }
  });
  await new Promise<void>((resolve) => other.listen(0, "127.0.0.1", resolve));
  try {
    const { port } = other.address() as AddressInfo;
    await page.goto(`http://127.0.0.1:${port}/`);
    await expect(page).toHaveTitle("asked");
    // Every ask arrived, and every request named this host and port: `.finally` sets the title
    // however the asks end.
    expect(seen.map(({ url }) => url)).toEqual(expect.arrayContaining(["/", ...ASKED]));
    for (const { raw } of seen) expect(raw).toContain(`127.0.0.1:${port}`);
    for (const entry of seen) expect(JSON.stringify(entry)).not.toContain(token);
  } finally {
    other.closeAllConnections();
    await new Promise<void>((resolve) => other.close(() => resolve()));
  }
});
