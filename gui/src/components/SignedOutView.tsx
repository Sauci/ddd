import { Banner } from "../ui/Banner";

/** What the page shows once the server has refused its token, or it kept none: the address
 * `ddd gui` printed signs it in again. The sentence is the server's own refusal's. */
export function SignedOutView() {
  return (
    <main>
      <Banner tone="warning">
        Open the address <code>ddd gui</code> printed in its terminal.
      </Banner>
    </main>
  );
}
