import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, getSettle, getUnits, getVariable, postEdit } from "../api/client";
import { VariablePanelView } from "../components/VariablePanelView";
import { editOf, outsideVocabulary, rawOf, startingUnit } from "../lib/units";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  focusPicker: boolean;
  onClose: () => void;
}

const STALE =
  "A file changed on disk, so nothing was written. The panel now shows the files as they are.";

/** One variable's panel: its declarations, the unit they state, and a unit to settle on. */
export function VariablePanel({ name, revision, stopped, focusPicker, onClose }: Props) {
  const queries = useQueryClient();
  const variable = useQuery({
    queryKey: ["variable", name, revision],
    queryFn: () => getVariable(name),
    placeholderData: (previous) => previous,
  });
  const units = useQuery({
    queryKey: ["units", revision],
    queryFn: () => getUnits(),
    placeholderData: (previous) => previous,
  });
  // `undefined` until the reader chooses: the panel then settles on the owner's unit, the
  // direction the tool's own rule reads in, and says what that would change.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [changesShown, setChangesShown] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const target = chosen === undefined ? startingUnit(variable.data?.declarations ?? []) : chosen;
  const preview = useQuery({
    queryKey: ["settle", name, target, revision],
    queryFn: () => getSettle(name, "unit", rawOf(target)),
    enabled: variable.data !== undefined,
  });
  const apply = useMutation({
    mutationFn: () => {
      const edit = preview.data === undefined ? null : editOf(preview.data);
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onSuccess: () => {
      setChosen(undefined);
      setTyped(undefined);
      setChangesShown(false);
      setRefused(null);
    },
    onError: (error) =>
      setRefused(
        error instanceof ApiError && error.code === "stale"
          ? STALE
          : `The change was refused: ${error.message}`,
      ),
    onSettled: () => queries.invalidateQueries(),
  });

  if (variable.isError) {
    return (
      <Panel title={name} onClose={onClose}>
        <Banner tone="error">{variable.error.message}</Banner>
      </Panel>
    );
  }
  if (variable.data === undefined || units.data === undefined) {
    return (
      <Panel title={name} onClose={onClose}>
        <p className="quiet">Reading {name}…</p>
      </Panel>
    );
  }
  return (
    <VariablePanelView
      variable={variable.data}
      units={units.data}
      typed={typed ?? target ?? ""}
      // Never the target: opening the picker on the owner's unit must still list everything,
      // not just the entries that happen to contain it (the picker's own journey, and spec 5.3).
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(unit) => {
        setChosen(unit);
        setTyped(unit ?? "");
        setRefused(null);
      }}
      note={outsideVocabulary(units.data, target) ? "Not one of this project's units" : undefined}
      preview={preview.data ?? null}
      refusal={refused ?? (preview.error === null ? null : preview.error.message)}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      focusPicker={focusPicker}
      onClose={onClose}
    />
  );
}
