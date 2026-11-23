import type { NamesReply } from "../api/types";
import { GO_TO, goToList } from "../lib/goTo";
import { ComboBox } from "../ui/ComboBox";

export interface GoToViewProps {
  /** What the field holds. */
  typed: string;
  onTyped: (text: string) => void;
  /** The names the server answered for what is typed, or `undefined` while none is asked. */
  reply: NamesReply | undefined;
  /** A name picked from the list, or the text the field holds where Enter is pressed with no entry
   * focused: the caller goes to it where the answer holds it (`goToRoute`, lib/goTo.ts). */
  onGo: (name: string) => void;
  /** What was typed is over: Escape, or the focus leaving the field. */
  onClose: () => void;
  /** Why no name can be listed: the server's refusal, said under the field. */
  note?: string | undefined;
  /** The files of the project that did not load, as the banner under the masthead names them: the
   * list says no variable of a file that loaded matches, rather than that none does (`noName`). */
  unread?: readonly string[];
  isDisabled: boolean;
  /** Opens the list when this changes to a new value: Enter took nothing, and the answer of what
   * it was pressed on has come (`entered`, lib/goTo.ts). */
  listing?: number | null;
  /** Opens the list as the field takes the focus, and takes it: a story's, to photograph the list
   * open. */
  opened?: boolean;
}

/** The masthead's go-to (16:I14): a field taking a part of a variable's name, listing the names
 * the server finds holding it (`goToList`, lib/goTo.ts). A picture of its props. */
export function GoToView(props: GoToViewProps) {
  const list = goToList(props.reply, props.typed, props.note !== undefined, props.unread);
  return (
    <div className="goto">
      <ComboBox
        label={GO_TO}
        inputValue={props.typed}
        onInputChange={props.onTyped}
        sections={list.sections}
        footnote={list.footnote}
        empty={list.empty}
        onPick={props.onGo}
        onEnter={props.onGo}
        onClose={props.onClose}
        note={props.note}
        isDisabled={props.isDisabled}
        autoFocus={props.opened === true ? 1 : null}
        open={props.listing ?? null}
        menuTrigger={props.opened === true ? "focus" : "input"}
      />
    </div>
  );
}
