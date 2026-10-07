import { existsSync } from "node:fs";
import { createServer } from "node:http";
import { join } from "node:path";
import { writeHostileBaseline } from "./demo";
import { expect, test } from "./fixtures";

test("a page on another port cannot make ddd gui run a baseline's plugin", async ({
  page,
  gui,
}) => {
  // The baseline this journey asks `ddd gui` to compare against - never through the page itself,
  // only through the hostile page's own fetch below. Loading it loads its plugin, whose body
  // alone writes `ran` beside itself, well before anything validates it as a plugin at all
  // (`ddd.plugins`, `demo.ts`'s own doc on `writeHostileBaseline`).
  const baseline = writeHostileBaseline(gui.directory);

  // Signed in through the server's own address, the same first step every other journey takes,
  // exactly as a reader would be: the page trades the token at `/open` for the one it keeps in
  // its own origin's storage, and lands on `/project` (`signIn.ts`). Waited out here, so that
  // the hostile page below is opened by a browser already signed in.
  await page.goto(gui.address);
  await page.waitForURL(/\/project$/);

  // The hostile page: a server of its own, on another port of 127.0.0.1 - the same site as ddd
  // gui's own address, but a different origin. Two defences now hold against its fetch:
  // - It carries no credential. No cookie exists for `credentials: "include"` to offer, and the
  //   token is in the storage of ddd gui's own origin, out of this one's reach.
  // - The gate refuses it anyway: the browser marks it `Sec-Fetch-Site: same-site`, which
  //   `_from_elsewhere` (`server.py`) tells apart from a request the server's own page made.
  // Taking the gate out used to turn this journey red, the cookie riding along. It no longer
  // does: the request reaches the API with no credential, and is answered 401. The cookie's
  // leak is pinned by `loopback.spec.ts` now.
  // `mode: "no-cors"` is what a page with no business reading the answer actually sends: it
  // cannot read an opaque response either way, so it asks and moves on once the browser reports
  // the attempt settled, never mind to what.
  const port = new URL(gui.address).port;
  const asked = `http://127.0.0.1:${port}/api/compare?baseline=${encodeURIComponent(baseline)}`;
  const html = `<!doctype html>
<title>hostile</title>
<script>
fetch(${JSON.stringify(asked)}, { credentials: "include", mode: "no-cors" })
  .finally(() => { document.title = "asked"; });
</script>
`;
  const hostile = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "text/html" });
    response.end(html);
  });
  try {
    await new Promise<void>((resolve) => hostile.listen(0, "127.0.0.1", resolve));
    const address = hostile.address();
    if (address === null || typeof address === "string") {
      throw new Error("the hostile server did not bind a port of its own");
    }

    // Opened in the same context as the sign-in above, as the reader's own browser would open
    // it: whatever that context holds for 127.0.0.1, `credentials: "include"` offers to send.
    await page.goto(`http://127.0.0.1:${address.port}/`);
    await expect(page).toHaveTitle("asked");

    // The plugin never ran, so it never wrote the file its body writes first.
    expect(existsSync(join(gui.directory, "baseline", "ran"))).toBe(false);
  } finally {
    await new Promise<void>((resolve) => {
      hostile.close(() => resolve());
      hostile.closeAllConnections();
    });
  }
});
