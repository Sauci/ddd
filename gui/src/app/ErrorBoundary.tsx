import { Component, type ReactNode } from "react";
import type { Route } from "../lib/route";

interface Props {
  /** The route the page is drawn for: a route given anew lets go of what was caught. */
  route: Route;
  /** What is drawn in the page's place once it threw, from what was thrown. */
  fallback: (thrown: unknown) => ReactNode;
  children: ReactNode;
}

interface State {
  /** The route the page was last drawn for. */
  route: Route;
  /** What the page threw while it was drawn for that route, held in an object so that a thrown
   * `undefined` or `null` is held as well; `null` while it threw nothing. */
  caught: { thrown: unknown } | null;
}

/**
 * The page's one error boundary (15:I5), under the masthead and the banners, around the main
 * region: a screen that throws while it is drawn - a reply it cannot draw, say - takes with it what
 * the main region held and nothing above it, so that the masthead, the banners and the address stay
 * as they were. Without it React unmounted the whole page, leaving `#root` empty and saying nothing.
 *
 * Let go when the route changes, so that the page the reader goes to is drawn, and one that throws
 * again is caught again. Compared as the object `useRoute` holds, which stays the one it was last
 * handed until the reader moves: another page is always another route. A class, as a render's
 * throw is caught by nothing else React has.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { route: this.props.route, caught: null };

  static getDerivedStateFromError(thrown: unknown): Partial<State> {
    return { caught: { thrown } };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.route === state.route ? null : { route: props.route, caught: null };
  }

  render() {
    const { caught } = this.state;
    return caught === null ? this.props.children : this.props.fallback(caught.thrown);
  }
}
