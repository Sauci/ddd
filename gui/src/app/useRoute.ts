import { useCallback, useEffect, useState } from "react";
import {
  type Held,
  heldFollowing,
  heldGoingTo,
  hrefOf,
  parseRoute,
  type Route,
  replacing,
} from "../lib/route";

/** The page the address shows, a way to go to another one that the back button undoes, whether
 * the page still shows the route it was loaded with, and how many times the reader has followed a
 * link or moved through the history since.
 *
 * A selection in a table replaces the address, and so does a filter's text as typing pauses;
 * going to another page pushes one, so the back button leaves the page rather than walking back
 * through every row the reader clicked. Going to the address the page is at replaces it too, as a
 * browser does following a link to the address it shows (`replacing`): pressed again, a link adds
 * no step for Back to walk through.
 *
 * The third value is `true` until the reader first moves the page - any `navigate`, and any move
 * back or forward within the page to another route - and `false` from then on: the route the page
 * was loaded with was chosen by its address (a link from elsewhere, a bookmark, a typed address, a
 * reload), every later one by the reader. A move through history that leaves the route as it was,
 * such as a fragment navigation another window can make, keeps it (`arrivedAfter`, ruling
 * P19a-19). `removalAsked` (`lib/files.ts`) is what reads it.
 *
 * The fourth counts the followings: every `navigate` but a replacement the page asks for, and every
 * move through history to another route (`heldGoingTo`, `heldFollowing`). The Findings tab is
 * drawn anew at each, from the text its address asks for (16:I9).
 *
 * A route naming what no address can carry (`hrefOf` writes none, 15:I5) is gone to all the same,
 * the address left as it stands: handed none, `pushState` and `replaceState` keep the page's. */
export function useRoute(): [
  Route,
  (route: Route, options?: { replace?: boolean }) => void,
  boolean,
  number,
] {
  // The route, whether it is still the one the page was loaded with - which a link from
  // elsewhere, a bookmark, a typed address or a reload chose - rather than one the reader reached
  // within the page, and the followings since. One value, so that a move through history decides
  // the others from the route it leaves.
  const [held, setHeld] = useState<Held>(() => ({
    route: parseRoute(window.location.pathname, window.location.search),
    arrived: true,
    followings: 0,
  }));
  useEffect(() => {
    const followHistory = () => {
      const followed = parseRoute(window.location.pathname, window.location.search);
      setHeld((current) => heldFollowing(current, followed));
    };
    window.addEventListener("popstate", followHistory);
    return () => window.removeEventListener("popstate", followHistory);
  }, []);
  const navigate = useCallback((next: Route, options?: { replace?: boolean }) => {
    const replace = options?.replace === true;
    const here = parseRoute(window.location.pathname, window.location.search);
    if (replacing(here, next, replace)) {
      window.history.replaceState(null, "", hrefOf(next));
    } else {
      window.history.pushState(null, "", hrefOf(next));
    }
    setHeld((current) => heldGoingTo(current, next, replace));
  }, []);
  return [held.route, navigate, held.arrived, held.followings];
}
