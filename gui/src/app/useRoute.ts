import { useCallback, useEffect, useState } from "react";
import { hrefOf, parseRoute, type Route } from "../lib/route";

/** The page the address shows, and a way to go to another one that the back button undoes.
 *
 * A selection in a table replaces the address; going to another page pushes one, so the back
 * button leaves the page rather than walking back through every row the reader clicked. */
export function useRoute(): [Route, (route: Route, options?: { replace?: boolean }) => void] {
  const [route, setRoute] = useState(() =>
    parseRoute(window.location.pathname, window.location.search),
  );
  useEffect(() => {
    const followHistory = () =>
      setRoute(parseRoute(window.location.pathname, window.location.search));
    window.addEventListener("popstate", followHistory);
    return () => window.removeEventListener("popstate", followHistory);
  }, []);
  const navigate = useCallback((next: Route, options?: { replace?: boolean }) => {
    if (options?.replace) {
      window.history.replaceState(null, "", hrefOf(next));
    } else {
      window.history.pushState(null, "", hrefOf(next));
    }
    setRoute(next);
  }, []);
  return [route, navigate];
}
