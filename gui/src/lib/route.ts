/** Which of the project screen's three tabs is open. */
export type ProjectView = "graph" | "table" | "units";

export type Route =
  | { page: "start" }
  | { page: "project"; view: Exclude<ProjectView, "units">; variable?: string }
  | { page: "project"; view: "units"; unit?: string }
  | { page: "component"; file: string; variable?: string };

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
    return variable === undefined
      ? { page: "project", view: "graph" }
      : { page: "project", view: "graph", variable };
  }
  const file = query.get("file");
  if (pathname === "/component" && file) {
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
      return variable === "" ? "/project" : `/project?${variable}`;
    case "component": {
      const file = `/component?file=${encodeURIComponent(route.file)}`;
      return variable === "" ? file : `${file}&${variable}`;
    }
  }
}
