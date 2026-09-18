import { expect, test } from "vitest";
import { hrefOf, parseRoute } from "./route";

test.each([
  ["/", "", { page: "start" }],
  ["/project", "", { page: "project", view: "graph" }],
  ["/project", "?view=graph", { page: "project", view: "graph" }],
  ["/project", "?view=table", { page: "project", view: "table" }],
  ["/project", "?view=sideways", { page: "project", view: "graph" }],
  ["/component", "?file=C%3A%2Fp%2Fa.ddd.json", { page: "component", file: "C:/p/a.ddd.json" }],
  ["/component", "", { page: "start" }],
  ["/elsewhere", "", { page: "start" }],
] as const)("%s%s is the %o page", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [{ page: "start" }, "/"],
  [{ page: "project", view: "graph" }, "/project"],
  [{ page: "project", view: "table" }, "/project?view=table"],
  [{ page: "component", file: "C:/p/a b.ddd.json" }, "/component?file=C%3A%2Fp%2Fa%20b.ddd.json"],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});

test.each([
  ["/project", "?variable=ValueA", { page: "project", view: "graph", variable: "ValueA" }],
  ["/project", "?view=table&variable=ValueA", { page: "project", view: "table" }],
  [
    "/component",
    "?file=C%3A%2Fp%2Fa.ddd.json&variable=Value%20A",
    { page: "component", file: "C:/p/a.ddd.json", variable: "Value A" },
  ],
  [
    "/component",
    "?file=C%3A%2Fp%2Fa.ddd.json&variable=",
    { page: "component", file: "C:/p/a.ddd.json" },
  ],
] as const)("%s%s carries the variable %o", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [{ page: "project", view: "graph", variable: "ValueA" }, "/project?variable=ValueA"],
  [
    { page: "component", file: "C:/p/a b.ddd.json", variable: "Value A" },
    "/component?file=C%3A%2Fp%2Fa%20b.ddd.json&variable=Value%20A",
  ],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});
