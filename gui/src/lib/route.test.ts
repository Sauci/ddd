import { expect, test } from "vitest";
import { hrefOf, parseRoute } from "./route";

test.each([
  ["/", "", { page: "start" }],
  ["/project", "", { page: "project" }],
  ["/component", "?file=C%3A%2Fp%2Fa.ddd.json", { page: "component", file: "C:/p/a.ddd.json" }],
  ["/component", "", { page: "start" }],
  ["/elsewhere", "", { page: "start" }],
] as const)("%s%s is the %o page", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [{ page: "start" }, "/"],
  [{ page: "project" }, "/project"],
  [{ page: "component", file: "C:/p/a b.ddd.json" }, "/component?file=C%3A%2Fp%2Fa%20b.ddd.json"],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});
