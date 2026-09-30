/** Which of the project screen's eight tabs is open. */
export type ProjectView =
  | "graph"
  | "table"
  | "units"
  | "types"
  | "shared"
  | "files"
  | "findings"
  | "compare";

export type Route =
  | { page: "start" }
  | { page: "project"; view: "graph"; variable?: string }
  | { page: "project"; view: "table" }
  | { page: "project"; view: "units"; unit?: string }
  | { page: "project"; view: "types"; type?: string }
  | { page: "project"; view: "shared" }
  | { page: "project"; view: "shared"; kind: "constant" | "section" | "raster"; name: string }
  // `path` is a row's key (`IncludedEntryReply.key`, or one of a pattern's own
  // `IncludedEntryReply.files`): the same absolute, posix-separated string `rowsOf` (lib/files.ts)
  // keys a row by, so the address a finding's `file` route writes (`routeOf` in lib/findings.ts)
  // and the one a reader's click writes select the very same row. Optional, as `units`' and
  // `types`' own selection is: the bare tab is a route of its own, not an absent one.
  | { page: "project"; view: "files"; path?: string }
  | { page: "project"; view: "findings" }
  | { page: "project"; view: "compare" }
  | { page: "component"; file: string; variable?: string }
  | { page: "component"; file: string; variable: string; view: "values" };

/** The page an address shows; anything unknown is the start page. */
export function parseRoute(pathname: string, search: string): Route {
  const query = new URLSearchParams(search);
  const variable = query.get("variable") || undefined;
  // The graph is what a bare /project opens on, so an address written before the tabs existed -
  // a bookmark, the masthead, a link in a message - still lands on the project screen. The graph
  // has a variable's panel beside it and the units tab a unit's; the table's rows open their
  // component instead.
  if (pathname === "/project") {
    const view = query.get("view");
    if (view === "table") return { page: "project", view: "table" };
    if (view === "units") {
      const unit = query.get("unit") || undefined;
      return unit === undefined
        ? { page: "project", view: "units" }
        : { page: "project", view: "units", unit };
    }
    if (view === "types") {
      const type = query.get("type") || undefined;
      return type === undefined
        ? { page: "project", view: "types" }
        : { page: "project", view: "types", type };
    }
    if (view === "shared") {
      // `kind` names which of the tab's vocabularies the selection is - "constant", "section" or
      // "raster" - and a `kind` none of those, a `kind` with no `name`, or no `kind` at all, is as
      // bare an address as the tab itself: a half-written address is the tab, never a crash and
      // never a guess at what it meant to select. One shape only: `isDeclared` on the tab's own
      // side is what turns a name nothing declares into the add form, pre-filled - so the address
      // that reaches it is the very same one a declared name's own panel opens from (design §2,
      // "one route kind, and the page decides").
      const kind = query.get("kind");
      const name = query.get("name") || undefined;
      return (kind === "constant" || kind === "section" || kind === "raster") && name !== undefined
        ? { page: "project", view: "shared", kind, name }
        : { page: "project", view: "shared" };
    }
    if (view === "files") {
      const path = query.get("path") || undefined;
      return path === undefined
        ? { page: "project", view: "files" }
        : { page: "project", view: "files", path };
    }
    if (view === "findings") return { page: "project", view: "findings" };
    if (view === "compare") return { page: "project", view: "compare" };
    return variable === undefined
      ? { page: "project", view: "graph" }
      : { page: "project", view: "graph", variable };
  }
  const file = query.get("file");
  if (pathname === "/component" && file) {
    if (query.get("view") === "values" && variable !== undefined) {
      return { page: "component", file, variable, view: "values" };
    }
    return variable === undefined
      ? { page: "component", file }
      : { page: "component", file, variable };
  }
  return { page: "start" };
}

/** The address of a page. */
export function hrefOf(route: Route): string {
  const variable =
    "variable" in route && route.variable !== undefined
      ? `variable=${encodeURIComponent(route.variable)}`
      : "";
  switch (route.page) {
    case "start":
      return "/";
    case "project":
      if (route.view === "table") return "/project?view=table";
      if (route.view === "units") {
        return route.unit === undefined
          ? "/project?view=units"
          : `/project?view=units&unit=${encodeURIComponent(route.unit)}`;
      }
      if (route.view === "types") {
        return route.type === undefined
          ? "/project?view=types"
          : `/project?view=types&type=${encodeURIComponent(route.type)}`;
      }
      if (route.view === "shared") {
        return "kind" in route
          ? `/project?view=shared&kind=${route.kind}&name=${encodeURIComponent(route.name)}`
          : "/project?view=shared";
      }
      if (route.view === "files") {
        return route.path === undefined
          ? "/project?view=files"
          : `/project?view=files&path=${encodeURIComponent(route.path)}`;
      }
      if (route.view === "findings") return "/project?view=findings";
      if (route.view === "compare") return "/project?view=compare";
      return variable === "" ? "/project" : `/project?${variable}`;
    case "component": {
      const file = `/component?file=${encodeURIComponent(route.file)}`;
      const address = variable === "" ? file : `${file}&${variable}`;
      return "view" in route ? `${address}&view=values` : address;
    }
  }
}
