import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";

export interface UndrawnViewProps {
  /** What failed, as `undrawnSentence` (lib/undrawn.ts) says it. */
  failure: string;
  /** The server has stopped answering: no reload is offered then. */
  stopped: boolean;
  onReload: () => void;
}

/** What the page's main region holds in place of a page that threw while it was drawn (15:I5),
 * under the masthead and the banners, which stay drawn: what failed, and a reload while the server
 * answers. None while it has stopped, when a reload would lose the page, and the banner above says
 * to start it again. */
export function UndrawnView({ failure, stopped, onReload }: UndrawnViewProps) {
  return (
    <main>
      <Banner tone="error">{failure}</Banner>
      {!stopped && (
        <Button variant="primary" onPress={onReload}>
          Reload the page
        </Button>
      )}
    </main>
  );
}
