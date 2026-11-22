import { undrawnSentence } from "../lib/undrawn";
import { UndrawnView } from "./UndrawnView";

export default { title: "Components / UndrawnView" };

/** A component's page whose findings came without their routes, a reply it cannot draw, while the
 * server answers: what failed, in the words of what was thrown, and a reload. */
export const AReplyItCannotDraw = () => (
  <UndrawnView
    failure={undrawnSentence(new TypeError("Cannot read properties of undefined (reading 'kind')"))}
    stopped={false}
    onReload={() => undefined}
  />
);
