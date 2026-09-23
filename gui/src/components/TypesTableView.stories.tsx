import { useState } from "react";
import type { TypesReply } from "../api/types";
import { NO_TYPES, PROJECT_TYPES } from "../stories/fixtures";
import { TypesTableView } from "./TypesTableView";

export default { title: "Components / TypesTableView" };

/** Holds its own selection, as the tab would: `on` seeds it, a click in the table moves it. */
function Tab({
  types = PROJECT_TYPES,
  on,
  unreadable = [],
}: {
  types?: TypesReply;
  on?: string;
  unreadable?: readonly string[];
}) {
  const [selected, setSelected] = useState<string | undefined>(on);
  return (
    <TypesTableView
      types={types}
      selected={selected}
      onSelect={setSelected}
      unreadable={unreadable}
    />
  );
}

/** The mockups' six types: one scalar, four structures, one external, none selected. */
export const AllThreeKinds = () => <Tab />;

/** Temperature_t's row marked, as opening its panel would leave it. */
export const Selected = () => <Tab on="Temperature_t" />;

/** A project that declares none: the sentence alone, no table under it. */
export const NothingDeclared = () => <Tab types={NO_TYPES} />;

/** types.ddd.json did not load: the warning above the list of what did load. */
export const AFileDidNotLoad = () => <Tab unreadable={["types.ddd.json"]} />;
