import type { IncomingHttpHeaders } from "node:http";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { expect, test } from "./fixtures";

// Part 18b's reason: a browser sends a cookie to every port of 127.0.0.1, and ddd gui's cookie
// was its token. Signed in through the printed address, the browser is taken to a server of
// its own on another port of the address, whose page then asks that server again, as any page
// landed on there may. That server records every header of every request, and the token is in
// none of them: no cookie carries it, and the page's own storage is out of this origin's reach.
test("another server on 127.0.0.1 is sent nothing of ddd gui's", async ({ page, gui }) => {
  const token = new URL(gui.address).searchParams.get("token");
  if (token === null) throw new Error(`ddd gui printed an address with no token: ${gui.address}`);
  await page.goto(gui.address);
  await page.waitForURL(/\/project$/);

  const seen: IncomingHttpHeaders[] = [];
  const other = createServer((request, response) => {
    seen.push(request.headers);
    if (request.url === "/") {
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      response.end(
        '<!doctype html><title>other</title><script>fetch("/again", { credentials: "include" })' +
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
    expect(seen.map((headers) => headers.host)).toContain(`127.0.0.1:${port}`);
    expect(seen.length).toBeGreaterThanOrEqual(2);
    for (const headers of seen) expect(JSON.stringify(headers)).not.toContain(token);
  } finally {
    other.closeAllConnections();
    await new Promise<void>((resolve) => other.close(() => resolve()));
  }
});
