import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { getNames } from "../api/client";
import { useDebounced } from "../app/useDebounced";
import { GoToView } from "../components/GoToView";
import { filterText } from "../lib/filter";
import { type Entered, entered, ownAnswer } from "../lib/goTo";
import type { Route } from "../lib/route";

interface Props {
  /** The open project's newest revision, whose index the names are asked of. */
  revision: number;
  stopped: boolean;
  /** Going to the page a name opens on, which the app navigates to. */
  onGo: (route: Route) => void;
}

/** The masthead's go-to (16:I14): what is typed asked of the server once typing pauses, as every
 * typed field asks (`useDebounced`), and the list the answer makes; a name picked, or spelled
 * exactly and Enter pressed, goes to its component's page with its panel open, and empties the
 * field for the next. The answer for the text before stays listed while the next is asked. Enter
 * is a commit: a text the answer in hand does not hold is asked for at once, and gone to - or the
 * list opened on its answer - once that answer has come (`entered`). */
export function GoTo({ revision, stopped, onGo }: Props) {
  // What the field holds, and whether Enter was pressed on it and waits for its answer: any change
  // of the text lets that Enter go.
  const [field, setField] = useState({ typed: "", entered: false });
  // A new number each time the list is to open on an answer Enter waited for.
  const [listing, setListing] = useState<number | null>(null);
  const asking = useDebounced(filterText(field.typed), !field.entered);
  const names = useQuery({
    queryKey: ["names", revision, asking],
    queryFn: () => getNames(asking),
    enabled: asking !== "",
    placeholderData: (previous) => previous,
  });
  const own = ownAnswer(names.data, names.isPlaceholderData, asking, field.typed);
  // What Enter on `typed`, or a pick, came to: the page gone to, the list opened, or Enter waiting.
  const settle = useCallback(
    (outcome: Entered | null, typed: string) => {
      if (outcome === null) return;
      if (outcome === "ask") {
        setField({ typed, entered: true });
        return;
      }
      setField({ typed: outcome === "list" ? typed : "", entered: false });
      if (outcome === "list") setListing((count) => (count ?? 0) + 1);
      else onGo(outcome.go);
    },
    [onGo],
  );
  // The answer Enter waited for, come at last.
  useEffect(() => {
    if (field.entered && own !== undefined) settle(entered(field.typed, own, own), field.typed);
  }, [field, own, settle]);
  return (
    <GoToView
      typed={field.typed}
      onTyped={(typed) => setField({ typed, entered: false })}
      reply={names.data}
      onGo={(name) => settle(entered(name, names.data, own), field.typed)}
      onClose={() => setField({ typed: "", entered: false })}
      note={names.error?.message}
      isDisabled={stopped}
      listing={listing}
    />
  );
}
