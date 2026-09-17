export type Route = { page: "start" } | { page: "project" } | { page: "component"; file: string };

/** The page an address shows; anything unknown is the start page. */
export function parseRoute(pathname: string, search: string): Route {
  if (pathname === "/project") return { page: "project" };
  const file = new URLSearchParams(search).get("file");
  if (pathname === "/component" && file) return { page: "component", file };
  return { page: "start" };
}

/** The address of a page. */
export function hrefOf(route: Route): string {
  switch (route.page) {
    case "start":
      return "/";
    case "project":
      return "/project";
    case "component":
      return `/component?file=${encodeURIComponent(route.file)}`;
  }
}
