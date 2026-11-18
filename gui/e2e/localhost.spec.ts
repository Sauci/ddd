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
  // ddd gui listens on [::1] itself, beside 127.0.0.1 on the same port, on every system and
  // exclusively on windows (12:I1, ruling B7-2), so the bind must be refused: EADDRINUSE on the
  // linux development PC, as measured. Which of the two windows gives was not recorded, so either
  // is taken.
  expect(["EADDRINUSE", "EACCES"]).toContain(await listenRefusal(port, "::1"));

  // A browser opening localhost may try [::1] first, and ddd gui answers there as it answers on
  // 127.0.0.1: the page, signed in by the token the address carries.
  const token = address.searchParams.get("token");
  await page.goto(`http://localhost:${port}/open?token=${token}`);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});
