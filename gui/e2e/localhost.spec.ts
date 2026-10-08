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
  // ddd gui holds [::1] on linux, and the wildcard [::] in its place on windows, listening on
  // neither (part 19a), so the bind must be refused: EADDRINUSE on the linux development PC, as
  // measured. Which of the two windows gives was not recorded, so either is taken.
  expect(["EADDRINUSE", "EACCES"]).toContain(await listenRefusal(port, "::1"));

  // Part 18b's review saw Chrome 153 send localhost to a program listening on [::1], three
  // times of three. On windows the wildcard [::] is held instead (part 19a, P19a-14), and
  // nothing listens on IPv6, so [::1] is refused there too, and ddd gui answers through
  // 127.0.0.1: chromium took 1.1 s in run 37752340092 and 1.0 s in run 37760106344, and
  // msedge 1.2 s and 845 ms in those same two runs.
  const token = address.searchParams.get("token");
  await page.goto(`http://localhost:${port}/open?token=${token}`);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});
