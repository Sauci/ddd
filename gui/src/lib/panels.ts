import type { PlanReply } from "../api/types";

/** What a panel offers for one action: the plan it would apply, why it was refused, and whether
 * what is shown is an earlier plan kept on screen while this one is asked for.
 *
 * One declaration for every panel rather than one apiece. The shape is structure, not a fact
 * about a vocabulary - `used()` in `SharedTableView` is deliberately not shared because a count's
 * wording *is* such a fact, and the design keeps those concrete (design §2). Which of a panel's
 * keys change with every keystroke, and so make a plan pending, differs by vocabulary and stays
 * documented in the panel it is true of. */
export interface Offer {
  /** The plan; `null` while it is being asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** The plan shown is an earlier one's, kept on screen while this one is asked for. It cannot be
   * applied. The panel's own doc says which of its keys put it in this state. */
  pending: boolean;
}
