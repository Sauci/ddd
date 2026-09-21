import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, getSettle, getUnits, getVariable, postEdit } from "../api/client";
import { VariablePanelView } from "../components/VariablePanelView";
import { editOf, outsideVocabulary, textOf } from "../lib/units";
import { labelOfRaw, limitsOf, limitsRaw, startingRaw } from "../lib/variableKeys";
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

/** One variable's panel: its keys, what each declaration says of them, and a key to settle. */
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
  const [selected, setSelected] = useState<string | undefined>(undefined);
  // `undefined` until the reader chooses: the chooser then settles on the producer's value, the
  // direction the tool's own rule reads in, and says what that would change.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [range, setRange] = useState<{ min: string; max: string }>({ min: "", max: "" });
  const [changesShown, setChangesShown] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const target =
    selected === undefined || variable.data === undefined
      ? null
      : chosen === undefined
        ? startingRaw(variable.data, selected)
        : chosen;
  const preview = useQuery({
    queryKey: ["settle", name, selected, target, revision],
    queryFn: () => getSettle(name, selected as string, target),
    enabled: variable.data !== undefined && selected !== undefined,
  });
  // Selecting a row starts that key afresh - what was chosen for the last one means nothing for
  // this one.
  const select = (key: string | undefined) => {
    setSelected(key);
    setChosen(undefined);
    setTyped(undefined);
    setChangesShown(false);
    setRefused(null);
    setRange(
      key === undefined || variable.data === undefined
        ? { min: "", max: "" }
        : limitsOf(startingRaw(variable.data, key)),
    );
  };
  // The unit cell of the component table hands the reader over to the unit's chooser, which is
  // what `focusPicker` has always asked for; it now says which row to open as well.
  // biome-ignore lint/correctness/useExhaustiveDependencies: select is rebuilt every render and reads only state setters and the latest data.
  useEffect(() => {
    if (focusPicker !== null) select("unit");
  }, [focusPicker]);
  // A range typed into the two fields is the value chosen as soon as it is a range.
  const onRange = (next: { min: string; max: string }) => {
    setRange(next);
    const raw = limitsRaw(next.min, next.max);
    // A half-typed range is not a choice: the preview keeps showing the last whole one.
    if (raw !== null) {
      setChosen(raw);
      setRefused(null);
    }
  };
  const apply = useMutation({
    mutationFn: () => {
      const edit = preview.data === undefined ? null : editOf(preview.data);
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    // The value chosen stays chosen: the panel then says there is nothing left to change. Let
    // go, it fell back on the producer's value in the declarations still on screen, which are
    // the ones the edit has just changed, and previewed undoing it.
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
      selected={selected}
      onSelect={select}
      chosen={target}
      typed={typed ?? (selected === undefined ? "" : labelOfRaw(variable.data, selected, target))}
      // Never the target: opening the list on the producer's value must still list everything,
      // not just the entries that happen to contain it (spec 5.3, and part 1's own journey).
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
        setRefused(null);
        if (selected === "limits") setRange(limitsOf(raw));
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={onRange}
      note={
        selected === "unit" && outsideVocabulary(units.data, textOf(target ?? undefined))
          ? "Not one of this project's units"
          : undefined
      }
      preview={preview.data ?? null}
      refusal={refused ?? (preview.error === null ? null : preview.error.message)}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      focus={focusPicker}
      onClose={onClose}
    />
  );
}
