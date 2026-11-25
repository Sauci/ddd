import { Banner } from "../ui/Banner";

/** What the page shows once the server has refused its token, or it kept none: the address
 * `ddd gui` printed signs it in again, once - an address already opened does not take the token
 * back, and the terminal's own line for a launch code presented again says to start `ddd gui`
 * again and open the address it prints then, as this does (the first words are the server's own
 * refusal's). */
export function SignedOutView() {
  return (
    <main>
      <Banner tone="warning">
        Open the address <code>ddd gui</code> printed in its terminal, or, if that address was
        opened already, stop <code>ddd gui</code> (Ctrl+C), start it again and open the address it
        prints then.
      </Banner>
    </main>
  );
}
