import { useCallback, useEffect, useState } from "react";
import { hrefOf, parseRoute, type Route } from "../lib/route";

/** The page the address shows, and a way to go to another one that the back button undoes. */
export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState(() =>
    parseRoute(window.location.pathname, window.location.search),
  );
  useEffect(() => {
    const followHistory = () =>
      setRoute(parseRoute(window.location.pathname, window.location.search));
    window.addEventListener("popstate", followHistory);
    return () => window.removeEventListener("popstate", followHistory);
  }, []);
  const navigate = useCallback((next: Route) => {
    window.history.pushState(null, "", hrefOf(next));
    setRoute(next);
  }, []);
  return [route, navigate];
}
