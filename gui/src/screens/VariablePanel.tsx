import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, getSettle, getUnits, getVariable, postEdit } from "../api/client";
import { VariablePanelView } from "../components/VariablePanelView";
import { editOf, outsideVocabulary, textOf } from "../lib/units";
import {
  keyRows,
  labelOfRaw,
  limitsNote,
  limitsOf,
  limitsRaw,
  startingRaw,
} from "../lib/variableKeys";
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
  // The reader's own choice of key, kept as a tri-state the way `chosen` below is: `undefined`
  // until they choose, `null` once they let a row go, a string for the key they picked.
  const [picked, setPicked] = useState<string | null | undefined>(undefined);
  // `undefined` until the reader chooses: the chooser then settles on the producer's value, the
  // direction the tool's own rule reads in, and says what that would change.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [range, setRange] = useState<{ min: string; max: string }>({ min: "", max: "" });
  const [changesShown, setChangesShown] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  // What the table actually offers to settle (`kind` aside): what a key remembered from a
  // previous variable, or forced by `focusPicker`, has to be checked against before it is shown.
  const rows =
    variable.data === undefined ? [] : keyRows(variable.data, null).filter((row) => row.settleable);
  // The key actually shown: the reader's own choice, once made and still one the table lists;
  // else the first row that disagrees - spec 5.1's own order, and what a red arrow on the canvas
  // is about, since it opens this panel because something disagrees and a reader could settle it
  // from there in one press; else none.
  const selected =
    picked === null
      ? undefined
      : picked !== undefined
        ? rows.find((row) => row.key === picked)?.key
        : rows.find((row) => row.disagrees)?.key;
  // `limits` is the one key with fields of its own, and they are what the panel would write:
  // the target is read back from them rather than kept beside them, so that what the two
  // fields say and what Apply writes cannot drift apart. Two empty fields are "state nothing",
  // which the list offers too; anything else that is not a range is not a value at all, and
  // the chooser says so instead of previewing something the reader did not ask for.
  const broken = selected === "limits" ? limitsNote(range.min, range.max) : null;
  const target =
    selected === undefined || variable.data === undefined || broken !== null
      ? null
      : selected === "limits"
        ? limitsRaw(range.min, range.max)
        : chosen === undefined
          ? startingRaw(variable.data, selected)
          : chosen;
  const preview = useQuery({
    queryKey: ["settle", name, selected, target, revision],
    queryFn: () => getSettle(name, selected as string, target),
    enabled: variable.data !== undefined && selected !== undefined && broken === null,
  });
  // Selecting a row starts that key afresh - what was chosen for the last one means nothing for
  // this one. Letting a row go is a choice too, not a blank: it must show the table alone even
  // while a row still disagrees, not hand the reader straight back to it.
  const select = (key: string | undefined) => {
    setPicked(key ?? null);
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
  // A range typed into the two fields is read straight back out of them by `target` above,
  // so there is nothing to remember here: a half-typed one leaves no whole one behind to be
  // applied in its place.
  const onRange = (next: { min: string; max: string }) => {
    setRange(next);
    setTyped(undefined);
    setRefused(null);
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
      // A range the fields do not make is no value, so the field above them reads empty and
      // the note says why, rather than naming a value nothing would be settled on.
      typed={
        typed ??
        (selected === undefined || broken !== null
          ? ""
          : labelOfRaw(variable.data, selected, target))
      }
      // Never the target: opening the list on the producer's value must still list everything,
      // not just the entries that happen to contain it (spec 5.3, and part 1's own journey).
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
        setRefused(null);
        // A range chosen from the list - one in play, or "state nothing", which empties them -
        // is settled on by writing it into the two fields, since they are what is applied.
        if (selected === "limits") setRange(limitsOf(raw));
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={onRange}
      note={
        broken ??
        (selected === "unit" && outsideVocabulary(units.data, textOf(target ?? undefined))
          ? "Not one of this project's units"
          : undefined)
      }
      // Nothing is previewed while the fields say nothing to apply, whatever this key was
      // previewed on before: the query is not asked, and an answer it kept is not shown.
      preview={broken === null ? (preview.data ?? null) : null}
      // A settlement refused is about the value that was asked for; while the fields make no
      // value, nothing was asked, and the note is the whole of what the panel has to say.
      refusal={
        refused ?? (broken !== null || preview.error === null ? null : preview.error.message)
      }
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      focus={focusPicker}
      onClose={onClose}
    />
  );
}
