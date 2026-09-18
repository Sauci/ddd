/** Which of the project screen's two tabs is open. */
export type ProjectView = "graph" | "table";

export type Route =
  | { page: "start" }
  | { page: "project"; view: ProjectView }
  | { page: "component"; file: string };

/** The page an address shows; anything unknown is the start page. */
export function parseRoute(pathname: string, search: string): Route {
  const query = new URLSearchParams(search);
  // The graph is what a bare /project opens on, so an address written before the tabs existed -
  // a bookmark, the masthead, a link in a message - still lands on the project screen.
  if (pathname === "/project") {
    return { page: "project", view: query.get("view") === "table" ? "table" : "graph" };
  }
  const file = query.get("file");
  if (pathname === "/component" && file) return { page: "component", file };
  return { page: "start" };
}

/** The address of a page. */
export function hrefOf(route: Route): string {
  switch (route.page) {
    case "start":
      return "/";
    case "project":
      return route.view === "table" ? "/project?view=table" : "/project";
    case "component":
      return `/component?file=${encodeURIComponent(route.file)}`;
  }
}
