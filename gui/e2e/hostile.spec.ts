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

  // Opening the server's own address in this context is what stores its `SameSite=Strict`
  // cookie - the same first step every other journey takes, signed in exactly as a reader would
  // be. `/open` answers with a page that refreshes itself to `/project` (`SIGNED_IN_PAGE`,
  // `server.py`); waited out here, rather than left in flight, so that navigating to the
  // hostile page below is not itself read as interrupting that still-pending refresh.
  await page.goto(gui.address);
  await page.waitForURL(/\/project$/);

  // The hostile page: a server of its own, on another port of 127.0.0.1 - the same site as ddd
  // gui's own address, so the cookie above rides along once asked for under `credentials:
  // "include"`, but a different origin, which is exactly what a browser's own `Sec-Fetch-Site:
  // same-site` (and `_from_elsewhere`, `server.py`) tell apart from a request the server's own
  // page made. `mode: "no-cors"` is what a page with no business reading the answer actually
  // sends: it cannot read an opaque response either way, so it asks and moves on once the
  // browser reports the attempt settled, never mind to what.
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

    // Opened in the same context as the sign-in above, so its cookie is the one `credentials:
    // "include"` offers to send.
    await page.goto(`http://127.0.0.1:${address.port}/`);
    await expect(page).toHaveTitle("asked");

    // The gate held: the plugin never ran, so it never wrote the file its body writes first.
    expect(existsSync(join(gui.directory, "baseline", "ran"))).toBe(false);
  } finally {
    await new Promise<void>((resolve) => {
      hostile.close(() => resolve());
      hostile.closeAllConnections();
    });
  }
});
