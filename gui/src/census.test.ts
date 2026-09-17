import { expect, test } from "vitest";

// Every logic module is imported, so the coverage gate also sees a module no test touches.
const modules = import.meta.glob(["./api/*.ts", "./lib/*.ts", "./state/*.ts", "!./**/*.test.ts"], {
  eager: true,
});

test("every logic module is loaded under the coverage gate", () => {
  expect(Object.keys(modules).length).toBeGreaterThanOrEqual(7);
});
