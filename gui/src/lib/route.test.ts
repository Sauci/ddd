import { expect, test } from "vitest";
import {
  arrivedAfter,
  type Held,
  heldFollowing,
  heldGoingTo,
  hrefOf,
  parseRoute,
  type Route,
  replacing,
  tabHref,
  takesWindow,
} from "./route";

test.each([
  ["/", "", { page: "start" }],
  ["/project", "", { page: "project", view: "graph" }],
  ["/project", "?view=graph", { page: "project", view: "graph" }],
  ["/project", "?view=table", { page: "project", view: "table" }],
  ["/project", "?view=findings", { page: "project", view: "findings" }],
  ["/project", "?view=compare", { page: "project", view: "compare" }],
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
  [{ page: "project", view: "findings" }, "/project?view=findings"],
  [{ page: "project", view: "compare" }, "/project?view=compare"],
  [{ page: "component", file: "C:/p/a b.ddd.json" }, "/component?file=C%3A%2Fp%2Fa%20b.ddd.json"],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});

test.each([
  ["/project", "?variable=ValueA", { page: "project", view: "graph", variable: "ValueA" }],
  ["/project", "?view=table&variable=ValueA", { page: "project", view: "table" }],
  ["/project", "?view=findings&variable=ValueA", { page: "project", view: "findings" }],
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

test.each([
  ["/project", "?view=units", { page: "project", view: "units" }],
  ["/project", "?view=units&unit=RPM", { page: "project", view: "units", unit: "RPM" }],
  ["/project", "?view=units&unit=%25", { page: "project", view: "units", unit: "%" }],
  ["/project", "?view=units&unit=", { page: "project", view: "units" }],
  ["/project", "?view=units&variable=ValueA", { page: "project", view: "units" }],
  ["/project", "?unit=RPM", { page: "project", view: "graph" }],
] as const)("%s%s carries the unit %o", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [{ page: "project", view: "units" }, "/project?view=units"],
  [{ page: "project", view: "units", unit: "RPM" }, "/project?view=units&unit=RPM"],
  [{ page: "project", view: "units", unit: "°C" }, "/project?view=units&unit=%C2%B0C"],
  [{ page: "project", view: "units", unit: "m/s" }, "/project?view=units&unit=m%2Fs"],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});

test.each([
  ["/project", "?view=types", { page: "project", view: "types" }],
  [
    "/project",
    "?view=types&type=Temperature_t",
    { page: "project", view: "types", type: "Temperature_t" },
  ],
  ["/project", "?view=types&type=%25", { page: "project", view: "types", type: "%" }],
  ["/project", "?view=types&type=", { page: "project", view: "types" }],
  ["/project", "?view=types&variable=ValueA", { page: "project", view: "types" }],
  ["/project", "?type=Temperature_t", { page: "project", view: "graph" }],
] as const)("%s%s carries the type %o", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [{ page: "project", view: "types" }, "/project?view=types"],
  [
    { page: "project", view: "types", type: "Temperature_t" },
    "/project?view=types&type=Temperature_t",
  ],
  [{ page: "project", view: "types", type: "Sensor_t" }, "/project?view=types&type=Sensor_t"],
  [{ page: "project", view: "types", type: "m/s_t" }, "/project?view=types&type=m%2Fs_t"],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});

test.each([
  ["/project", "?view=files", { page: "project", view: "files" }],
  [
    "/project",
    "?view=files&path=C%3A%2Fp%2Fa%20b.ddd.json",
    { page: "project", view: "files", path: "C:/p/a b.ddd.json" },
  ],
  // An empty `path`, like an empty `unit` or `type`, is as bare an address as leaving it out.
  ["/project", "?view=files&path=", { page: "project", view: "files" }],
] as const)("%s%s carries the files path %o", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [
    "/project",
    "?view=findings&text=controller.ddd.json",
    { page: "project", view: "findings", text: "controller.ddd.json" },
  ],
  [
    "/project",
    "?view=findings&text=a%2Fpump.ddd.json%20",
    { page: "project", view: "findings", text: "a/pump.ddd.json " },
  ],
  // An empty `text`, like an empty `path`, is as bare an address as leaving it out.
  ["/project", "?view=findings&text=", { page: "project", view: "findings" }],
  ["/project", "?view=table&text=controller.ddd.json", { page: "project", view: "table" }],
] as const)("%s%s carries the findings filter's text %o", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [
    { page: "project", view: "findings", text: "controller.ddd.json" },
    "/project?view=findings&text=controller.ddd.json",
  ],
  [
    { page: "project", view: "findings", text: "a/pump.ddd.json & co" },
    "/project?view=findings&text=a%2Fpump.ddd.json%20%26%20co",
  ],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});

test.each([
  [{ page: "project", view: "files" }, "/project?view=files"],
  [
    // A path holding characters an address must escape: `:`, `/` and the space, the same fixture
    // `/component?file=` is pinned with above.
    { page: "project", view: "files", path: "C:/p/a b.ddd.json" },
    "/project?view=files&path=C%3A%2Fp%2Fa%20b.ddd.json",
  ],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});

test("the shared files tab with nothing selected", () => {
  expect(parseRoute("/project", "?view=shared")).toEqual({ page: "project", view: "shared" });
  expect(hrefOf({ page: "project", view: "shared" })).toBe("/project?view=shared");
});

test("the shared files tab with a constant selected", () => {
  const route = {
    page: "project",
    view: "shared",
    kind: "constant",
    name: "TREND_SAMPLES",
  } as const;
  expect(parseRoute("/project", "?view=shared&kind=constant&name=TREND_SAMPLES")).toEqual(route);
  expect(hrefOf(route)).toBe("/project?view=shared&kind=constant&name=TREND_SAMPLES");
});

test("the shared files tab with a section selected", () => {
  const route = {
    page: "project",
    view: "shared",
    kind: "section",
    name: ".calib",
  } as const;
  expect(parseRoute("/project", "?view=shared&kind=section&name=.calib")).toEqual(route);
  expect(hrefOf(route)).toBe("/project?view=shared&kind=section&name=.calib");
});

test("a selection with no kind is the bare tab", () => {
  expect(parseRoute("/project", "?view=shared&name=TREND_SAMPLES")).toEqual({
    page: "project",
    view: "shared",
  });
});

test("a kind with no name is the bare tab too", () => {
  // `kind=constant` alone is as half-written an address as leaving `kind` out entirely.
  expect(parseRoute("/project", "?view=shared&kind=constant")).toEqual({
    page: "project",
    view: "shared",
  });
});

test("the shared files tab with a raster selected", () => {
  const route = {
    page: "project",
    view: "shared",
    kind: "raster",
    name: "10ms",
  } as const;
  expect(parseRoute("/project", "?view=shared&kind=raster&name=10ms")).toEqual(route);
  expect(hrefOf(route)).toBe("/project?view=shared&kind=raster&name=10ms");
});

test("a kind none of the tab's vocabularies spells is the bare tab too", () => {
  // A word naming no vocabulary at all is as unrecognised as a typo would be.
  expect(parseRoute("/project", "?view=shared&kind=nonsense&name=x")).toEqual({
    page: "project",
    view: "shared",
  });
});

test.each([
  [
    "/component",
    "?file=C%3A%2Fp%2Fa.ddd.json&variable=CurveA&view=values",
    { page: "component", file: "C:/p/a.ddd.json", variable: "CurveA", view: "values" },
  ],
  [
    // No variable, so there is nothing to open a grid on: today's plain component page.
    "/component",
    "?file=C%3A%2Fp%2Fa.ddd.json&view=values",
    { page: "component", file: "C:/p/a.ddd.json" },
  ],
] as const)("%s%s carries the values view %o", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [
    { page: "component", file: "C:/p/a.ddd.json", variable: "CurveA", view: "values" },
    "/component?file=C%3A%2Fp%2Fa.ddd.json&variable=CurveA&view=values",
  ],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});

// Every kind of route, as `parseRoute` reads its address: `hrefOf` writes each back as an address
// that reads as the very same route, so two routes `parseRoute` read compare as their addresses
// (`arrivedAfter`) exactly when they are one route.
test.each([
  ["/", ""],
  ["/project", ""],
  ["/project", "?variable=Value%20A"],
  ["/project", "?view=table"],
  ["/project", "?view=units"],
  ["/project", "?view=units&unit=%C2%B0C"],
  ["/project", "?view=types&type=m%2Fs_t"],
  ["/project", "?view=shared"],
  ["/project", "?view=shared&kind=raster&name=10ms"],
  ["/project", "?view=files"],
  ["/project", "?view=files&path=C%3A%2Fp%2Fa%20b.ddd.json"],
  ["/project", "?view=findings"],
  ["/project", "?view=findings&text=controller.ddd.json"],
  ["/project", "?view=compare"],
  ["/component", "?file=C%3A%2Fp%2Fa.ddd.json"],
  ["/component", "?file=C%3A%2Fp%2Fa.ddd.json&variable=CurveA"],
  ["/component", "?file=C%3A%2Fp%2Fa.ddd.json&variable=CurveA&view=values"],
  // The bytes utf-8 would give U+D800 alone, which it gives none: decoded, they are replacement
  // characters, a name an address carries.
  ["/project", "?view=units&unit=%ED%A0%80x"],
] as const)("%s%s is written back as an address of the same route", (pathname, search) => {
  const route = parseRoute(pathname, search);
  const href = hrefOf(route);
  // A route read off an address never names what no address can carry.
  if (href === null) throw new Error(`${pathname}${search} was read as a route with no address`);
  const written = new URL(href, "http://127.0.0.1");
  expect(parseRoute(written.pathname, written.search)).toEqual(route);
});

/** The two halves of a surrogate pair, each alone a string no address can carry: a json file can
 * state one as an escape, and the loader reads it as it is (15:I5). */
const HIGH = String.fromCharCode(0xd800);
const LOW = String.fromCharCode(0xdc00);

test.each([
  ["the graph's variable", { page: "project", view: "graph", variable: `${HIGH}x` }],
  ["a unit", { page: "project", view: "units", unit: `${HIGH}x` }],
  ["a type", { page: "project", view: "types", type: `x${LOW}` }],
  ["a shared entry", { page: "project", view: "shared", kind: "constant", name: `${HIGH}x` }],
  ["a Files row", { page: "project", view: "files", path: `C:/p/${LOW}.ddd.json` }],
  ["the findings filter's text", { page: "project", view: "findings", text: `${HIGH}.ddd.json` }],
  ["a component's file", { page: "component", file: `C:/p/${HIGH}.ddd.json` }],
  ["a component's variable", { page: "component", file: "C:/p/a.ddd.json", variable: `${HIGH}x` }],
  [
    "a values grid's variable",
    { page: "component", file: "C:/p/a.ddd.json", variable: `x${LOW}`, view: "values" },
  ],
] as const)("%s holding half of a surrogate pair alone has no address", (_, route) => {
  expect(hrefOf(route)).toBeNull();
});

test("a name holding a whole surrogate pair is carried, in utf-8", () => {
  const unit = String.fromCodePoint(0x1f321);
  expect(hrefOf({ page: "project", view: "units", unit })).toBe(
    "/project?view=units&unit=%F0%9F%8C%A1",
  );
});

// Every tab with nothing selected in it names nothing of the project's, so it always has an
// address: the one `hrefOf` writes for its bare route.
test.each(["graph", "table", "units", "types", "shared", "files", "findings", "compare"] as const)(
  "the %s tab's address is its bare route's",
  (view) => {
    expect(tabHref(view)).toBe(hrefOf(parseRoute("/project", `?view=${view}`)));
  },
);

/** A Files row's route, as the page was loaded with it. */
const ROW = parseRoute("/project", "?view=files&path=C%3A%2Fp%2Fa.ddd.json");

test("a move through history that leaves the route as it was keeps the page's arrival", () => {
  // A fragment navigation fires `popstate` with the path and the query as they were, and any window
  // holding a handle on this one - a cross-origin opener among them - can make one (ruling P19a-19).
  expect(
    arrivedAfter(true, ROW, parseRoute("/project", "?view=files&path=C%3A%2Fp%2Fa.ddd.json")),
  ).toBe(true);
});

test("one route keeps it however its address is spelled", () => {
  expect(
    arrivedAfter(
      true,
      ROW,
      parseRoute("/project", "?path=C%3A%2Fp%2Fa.ddd.json&view=files&from=x"),
    ),
  ).toBe(true);
});

test("a move through history to another route turns it false", () => {
  expect(arrivedAfter(true, ROW, parseRoute("/project", "?view=findings"))).toBe(false);
  expect(
    arrivedAfter(true, ROW, parseRoute("/project", "?view=files&path=C%3A%2Fp%2Fb.ddd.json")),
  ).toBe(false);
});

test("once false it stays false, on the route the page was loaded with too", () => {
  expect(arrivedAfter(false, ROW, ROW)).toBe(false);
});

/** The Findings tab's route asking for `text`, as a link of the banner under the masthead writes
 * it, or the bare tab. */
const findings = (text?: string): Route =>
  text === undefined
    ? { page: "project", view: "findings" }
    : { page: "project", view: "findings", text };

/** A page that has followed three links since it loaded, on the findings of controller.ddd.json. */
const HELD: Held = { route: findings("controller.ddd.json"), arrived: false, followings: 3 };

test("a link followed is a following, and a selection or a filter's text the page writes is none", () => {
  // 16:I9: the Findings tab is drawn anew at each following, from the text its address asks for,
  // and left as it is while the address follows what the reader types into its filter.
  expect(heldGoingTo(HELD, findings("sensor"), true)).toEqual({
    route: findings("sensor"),
    arrived: false,
    followings: 3,
  });
  expect(heldGoingTo({ ...HELD, arrived: true }, findings("sensor"), true).arrived).toBe(false);
  // Pressed again where the page is, a link is followed all the same: the reader asked for it.
  expect(heldGoingTo(HELD, findings("controller.ddd.json"), false)).toEqual({
    route: findings("controller.ddd.json"),
    arrived: false,
    followings: 4,
  });
});

test("a move through history to another route is a following, and one leaving the route as it was is none", () => {
  expect(heldFollowing(HELD, parseRoute("/project", "?view=findings&text=sensor"))).toEqual({
    route: findings("sensor"),
    arrived: false,
    followings: 4,
  });
  // A fragment navigation, which another window can make, however the address is spelled.
  expect(
    heldFollowing(HELD, parseRoute("/project", "?text=controller.ddd.json&view=findings")),
  ).toEqual({ route: findings("controller.ddd.json"), arrived: false, followings: 3 });
  // Whether the page still holds the route it was loaded with, as `arrivedAfter` says.
  const loaded = { ...HELD, arrived: true };
  expect(heldFollowing(loaded, findings("controller.ddd.json")).arrived).toBe(true);
  expect(heldFollowing(loaded, findings("sensor")).arrived).toBe(false);
});

test("going to the address the page is at replaces its entry in the history, as the page's own writes do", () => {
  // A link pressed again adds no step for Back to walk through, as a browser following a link to
  // the address it shows adds none.
  const here = parseRoute("/project", "?view=findings&text=controller.ddd.json");
  expect(replacing(here, findings("controller.ddd.json"), false)).toBe(true);
  expect(
    replacing(
      parseRoute("/project", "?text=controller.ddd.json&view=findings&from=x"),
      findings("controller.ddd.json"),
      false,
    ),
  ).toBe(true);
  // What the page writes of its own replaces it wherever it leads; a link to another address
  // adds a step.
  expect(replacing(here, findings("sensor"), true)).toBe(true);
  expect(replacing(here, findings("sensor"), false)).toBe(false);
  expect(replacing(here, findings(), false)).toBe(false);
  // A route no address can carry adds a step, the address left as it stands, as it did.
  expect(replacing(here, { page: "project", view: "units", unit: HIGH }, false)).toBe(false);
});

test.each([
  // The Graph and a component's values grid take the window; the 1,100 px measure stays for the rest
  // (decision 16.4).
  [{ page: "project", view: "graph" }, true],
  [{ page: "project", view: "graph", variable: "ValueA" }, true],
  [{ page: "component", file: "/p/a.ddd.json", variable: "ValueA", view: "values" }, true],
  [{ page: "project", view: "table" }, false],
  [{ page: "project", view: "findings" }, false],
  [{ page: "component", file: "/p/a.ddd.json" }, false],
  [{ page: "start" }, false],
] as const)("%o takes the window: %s", (route, takes) => {
  expect(takesWindow(route)).toBe(takes);
});
