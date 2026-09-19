/** Which of the project screen's two tabs is open. */
export type ProjectView = "graph" | "table";

export type Route =
  | { page: "start" }
  | { page: "project"; view: ProjectView; variable?: string }
  | { page: "component"; file: string; variable?: string };

/** The page an address shows; anything unknown is the start page. */
export function parseRoute(pathname: string, search: string): Route {
  const query = new URLSearchParams(search);
  const variable = query.get("variable") || undefined;
  // The graph is what a bare /project opens on, so an address written before the tabs existed -
  // a bookmark, the masthead, a link in a message - still lands on the project screen. Only the
  // graph has a panel beside it: the table's rows open their component instead.
  if (pathname === "/project") {
    if (query.get("view") === "table") return { page: "project", view: "table" };
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
      return variable === "" ? "/project" : `/project?${variable}`;
    case "component": {
      const file = `/component?file=${encodeURIComponent(route.file)}`;
      return variable === "" ? file : `${file}&${variable}`;
    }
  }
}
