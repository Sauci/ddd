import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, getSettle, getUnits, getVariable, postEdit } from "../api/client";
import { VariablePanelView } from "../components/VariablePanelView";
import { editOf, outsideVocabulary, rawOf, startingUnit, unitLabel } from "../lib/units";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  /** A new value on every request to focus the picker; `null` asks for no focus. */
  focusPicker: number | null;
  onClose: () => void;
  /** No file of the open project declares the variable: the page closes the panel, saying why. */
  onUndeclared: () => void;
}

const STALE =
  "A file changed on disk, so nothing was written. The panel now shows the files as they are.";

/** One variable's panel: its declarations, the unit they state, and a unit to settle on. */
export function VariablePanel({
  name,
  revision,
  stopped,
  focusPicker,
  onClose,
  onUndeclared,
}: Props) {
  const queries = useQueryClient();
  const variable = useQuery({
    queryKey: ["variable", name, revision],
    queryFn: () => getVariable(name),
    placeholderData: (previous) => previous,
  });
  // Spec 5.5: a variable renamed or removed on disk - or named by an address no file declares,
  // such as an old bookmark - is not declared any longer, and its panel closes. It says why on
  // the page it was beside rather than in a panel of its own, which is about to go. While a file
  // does not load the server cannot say that, and answers `unreadable` instead: the panel then
  // stays, naming the file, and shows the variable again once the file loads.
  const undeclared = variable.error instanceof ApiError && variable.error.code === "not-found";
  useEffect(() => {
    if (undeclared) onUndeclared();
  }, [undeclared, onUndeclared]);
  const units = useQuery({
    queryKey: ["units", revision],
    queryFn: () => getUnits(),
    placeholderData: (previous) => previous,
  });
  // `undefined` until the reader chooses: the panel then settles on the owner's unit, the
  // direction the tool's own rule reads in, and says what that would change.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  // What the reader is typing into the picker, `undefined` whenever its list is closed: the field
  // then reads the unit settled on, so the field, the consequence line and Show changes always
  // speak of the same unit.
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
    // The unit chosen stays chosen: the panel then says there is nothing left to change. Let go,
    // it fell back on the owner's unit in the declarations still on screen, which are the ones
    // the edit has just changed, and previewed undoing it.
    onSuccess: () => {
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
    // An Apply changes this variable's declarations, the units the project uses and the preview
    // it was made from, whose fingerprints the edit spent: those are asked for again, and Apply
    // stays unavailable until they answer. Everything else - the component's file, the canvas -
    // is keyed by revision, and moves on with the state the edit made.
    onSettled: () =>
      Promise.all([
        queries.invalidateQueries({ queryKey: ["variable", name] }),
        queries.invalidateQueries({ queryKey: ["units"] }),
        queries.invalidateQueries({ queryKey: ["settle", name] }),
      ]),
  });

  if (undeclared) return null;
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
      typed={typed ?? unitLabel(target)}
      // Never the target: opening the picker on the owner's unit must still list everything,
      // not just the entries that happen to contain it (the picker's own journey, and spec 5.3).
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(unit) => {
        setChosen(unit);
        setTyped(undefined);
        setRefused(null);
      }}
      onPickerClosed={() => setTyped(undefined)}
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
