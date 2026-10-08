import { useCallback, useEffect, useState } from "react";
import { hrefOf, parseRoute, type Route } from "../lib/route";

/** The page the address shows, a way to go to another one that the back button undoes, and
 * whether the page still shows the route it was loaded with.
 *
 * A selection in a table replaces the address; going to another page pushes one, so the back
 * button leaves the page rather than walking back through every row the reader clicked.
 *
 * The third value is `true` until the first navigation of the page's own - any `navigate`, and
 * any move back or forward within the page - and `false` from then on: the route the page was
 * loaded with was chosen by its address (a link from elsewhere, a bookmark, a typed address, a
 * reload), every later one by the reader. `removalAsked` (`lib/files.ts`) is what reads it. */
export function useRoute(): [
  Route,
  (route: Route, options?: { replace?: boolean }) => void,
  boolean,
] {
  const [route, setRoute] = useState(() =>
    parseRoute(window.location.pathname, window.location.search),
  );
  // Whether the route is still the one the page was loaded with - which a link from elsewhere,
  // a bookmark, a typed address or a reload chose - rather than one the reader reached within
  // the page. Any navigation, back and forward included, is the reader's.
  const [arrived, setArrived] = useState(true);
  useEffect(() => {
    const followHistory = () => {
      setArrived(false);
      setRoute(parseRoute(window.location.pathname, window.location.search));
    };
    window.addEventListener("popstate", followHistory);
    return () => window.removeEventListener("popstate", followHistory);
  }, []);
  const navigate = useCallback((next: Route, options?: { replace?: boolean }) => {
    if (options?.replace) {
      window.history.replaceState(null, "", hrefOf(next));
    } else {
      window.history.pushState(null, "", hrefOf(next));
    }
    setArrived(false);
    setRoute(next);
  }, []);
  return [route, navigate, arrived];
}
