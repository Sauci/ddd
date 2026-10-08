import { useCallback, useEffect, useState } from "react";
import { arrivedAfter, hrefOf, parseRoute, type Route } from "../lib/route";

/** The page the address shows, a way to go to another one that the back button undoes, and
 * whether the page still shows the route it was loaded with.
 *
 * A selection in a table replaces the address; going to another page pushes one, so the back
 * button leaves the page rather than walking back through every row the reader clicked.
 *
 * The third value is `true` until the reader first moves the page - any `navigate`, and any move
 * back or forward within the page to another route - and `false` from then on: the route the page
 * was loaded with was chosen by its address (a link from elsewhere, a bookmark, a typed address, a
 * reload), every later one by the reader. A move through history that leaves the route as it was,
 * such as a fragment navigation another window can make, keeps it (`arrivedAfter`, ruling
 * P19a-19). `removalAsked` (`lib/files.ts`) is what reads it. */
export function useRoute(): [
  Route,
  (route: Route, options?: { replace?: boolean }) => void,
  boolean,
] {
  // The route, and whether it is still the one the page was loaded with - which a link from
  // elsewhere, a bookmark, a typed address or a reload chose - rather than one the reader reached
  // within the page. One value, so that a move through history decides the second from the route
  // it leaves.
  const [held, setHeld] = useState(() => ({
    route: parseRoute(window.location.pathname, window.location.search),
    arrived: true,
  }));
  useEffect(() => {
    const followHistory = () => {
      const followed = parseRoute(window.location.pathname, window.location.search);
      setHeld((current) => ({
        route: followed,
        arrived: arrivedAfter(current.arrived, current.route, followed),
      }));
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
    setHeld({ route: next, arrived: false });
  }, []);
  return [held.route, navigate, held.arrived];
}
