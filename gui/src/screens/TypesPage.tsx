import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getTypes } from "../api/client";
import type { State } from "../api/types";
import { TypesTableView } from "../components/TypesTableView";
import type { Route } from "../lib/route";
import { baseName } from "../lib/units";
import { Banner } from "../ui/Banner";
import { TypePanel } from "./TypePanel";

interface Props {
  state: State | null;
  /** The type whose panel is open, as the address names it. */
  type: string | undefined;
  stopped: boolean;
  onType: (type: string | undefined) => void;
  /** Following a use, a member's type or a finding, without a reload. */
  onOpen: (route: Route) => void;
}

/** The open project's Types tab (spec 5.1): every type it declares, and the panel of the one
 * selected. `TypesTableView` draws the tab's own meta line and its unreadable-file warning; this
 * screen only says when a type's panel has closed because the type is gone (spec 5.4). */
export function TypesPage({ state, type, stopped, onType, onOpen }: Props) {
  const revision = state?.revision;
  const types = useQuery({
    queryKey: ["types", revision],
    queryFn: () => getTypes(),
    // The table stays while the next revision's types are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash.
    placeholderData: (previous) => previous,
  });
  // The type whose panel closed because nothing declares it any longer (spec 5.4), named above
  // the table until another type is selected or the reader leaves the tab.
  const [gone, setGone] = useState<string | null>(null);
  // The names of the types files that did not load, which declare types the table cannot show -
  // computed from the same state the rest of the page reads, since the server's own answer to
  // `GET /api/types` says nothing about a file it could not read at all.
  const unreadable = (state?.files ?? [])
    .filter((file) => file.kind === "types" && !file.loaded)
    .map((file) => baseName(file.path));

  if (types.data === undefined) {
    if (types.isError) return <Banner tone="error">{types.error.message}</Banner>;
    return <p className="quiet">Reading the project's types…</p>;
  }
  const select = (next: string | undefined) => {
    setGone(null);
    onType(next);
  };
  return (
    <>
      {/* A server that stopped answering leaves the table as it was, and says so above it. */}
      {types.isError && <Banner tone="error">{types.error.message}</Banner>}
      {gone !== null && (
        <Banner tone="warning">{gone} is no longer declared in the open project.</Banner>
      )}
      <div className={type !== undefined ? "with-panel" : undefined}>
        <div>
          <TypesTableView
            types={types.data}
            selected={type}
            onSelect={select}
            unreadable={unreadable}
          />
        </div>
        {type !== undefined && (
          <TypePanel
            key={type}
            name={type}
            revision={revision}
            stopped={stopped}
            onClose={() => onType(undefined)}
            onGone={() => {
              setGone(type);
              onType(undefined);
            }}
            onMoved={select}
            onOpen={onOpen}
          />
        )}
      </div>
    </>
  );
}
