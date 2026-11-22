import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getNames } from "../api/client";
import { useDebounced } from "../app/useDebounced";
import { GoToView } from "../components/GoToView";
import { filterText } from "../lib/filter";
import { goToRoute } from "../lib/goTo";
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
 * field for the next. The answer for the text before stays listed while the next is asked. */
export function GoTo({ revision, stopped, onGo }: Props) {
  const [typed, setTyped] = useState("");
  const asking = useDebounced(filterText(typed));
  const names = useQuery({
    queryKey: ["names", revision, asking],
    queryFn: () => getNames(asking),
    enabled: asking !== "",
    placeholderData: (previous) => previous,
  });
  return (
    <GoToView
      typed={typed}
      onTyped={setTyped}
      reply={names.data}
      onGo={(name) => {
        const route = goToRoute(names.data, name);
        if (route === null) return;
        setTyped("");
        onGo(route);
      }}
      onClose={() => setTyped("")}
      note={names.error?.message}
      isDisabled={stopped}
    />
  );
}
