import { createServer } from "node:net";
import { expect, test } from "./fixtures";

/** Whether a stranger can listen on `host` at `port`: the error it is refused with, or null. */
function listenRefusal(port: number, host: string): Promise<string | null> {
  return new Promise((resolve) => {
    const stranger = createServer();
    stranger.once("error", (error: NodeJS.ErrnoException) => resolve(error.code ?? "unknown"));
    stranger.listen(port, host, () => stranger.close(() => resolve(null)));
  });
}

test("localhost reaches ddd gui, and nothing else can listen on [::1] at its port", async ({
  page,
  gui,
}) => {
  const address = new URL(gui.address);
  const port = Number(address.port);
  // Held by ddd gui, never listened on (part 19a): the bind is refused - EADDRINUSE, or
  // EACCES where windows binds the port exclusively.
  expect(["EADDRINUSE", "EACCES"]).toContain(await listenRefusal(port, "::1"));

  // The browser tries [::1] first, is refused, and falls back to 127.0.0.1, where ddd gui
  // answers - on windows only after its own retries, which is what this journey's legs time.
  const token = address.searchParams.get("token");
  await page.goto(`http://localhost:${port}/open?token=${token}`);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});
