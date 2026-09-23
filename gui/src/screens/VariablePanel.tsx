import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  ApiError,
  getDeclarationPlan,
  getSettle,
  getUnits,
  getVariable,
  postEdit,
} from "../api/client";
import type { Offer } from "../components/UnitPanelView";
import { VariablePanelView } from "../components/VariablePanelView";
import { planEdit } from "../lib/projectUnits";
import { type Refused, shownRefusal } from "../lib/refusals";
import { removeLabel, settleLabel } from "../lib/undo";
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
  /** The component page this panel is open from, absolute and posix-separated - `undefined` on
   * the project screen's own panel, where no one component is in view and so no removal is
   * offered. */
  file: string | undefined;
  revision: number | undefined;
  stopped: boolean;
  /** A new value on every request to focus the picker; `null` asks for no focus. */
  focusPicker: number | null;
  onClose: () => void;
  /** No file of the open project declares the variable: the page closes the panel, saying why. */
  onUndeclared: () => void;
  /** Following a fixed key to the type that fixes it, without a reload - the project's Types
   * tab, since the type is the project's rather than this variable's own. */
  onOpenType: (name: string) => void;
}

const STALE =
  "A file changed on disk, so nothing was written. The panel now shows the files as they are.";

/** One variable's panel: its keys, what each declaration says of them, and a key to settle. */
export function VariablePanel({
  name,
  file,
  revision,
  stopped,
  focusPicker,
  onClose,
  onUndeclared,
  onOpenType,
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
  // What removing this declaration from `file` would take - asked for only on a component's
  // page, which is what `file` being stated says; the project screen's own panel offers no
  // removal, and asks for no plan.
  const removal = useQuery({
    queryKey: ["declaration-plan", "remove", file, name, revision],
    queryFn:
      file === undefined ? skipToken : () => getDeclarationPlan({ action: "remove", file, name }),
  });
  // Which component the removal would take the declaration from - this file's own name among
  // the variable's declarations - for the offer's sentence and the label its undo would carry.
  // `undefined` before the variable has loaded, or on the project screen, where `file` matches
  // none of them because there is none to match.
  const from = variable.data?.declarations.find((entry) => entry.path === file)?.component;
  // The reader's own choice of key, kept as a tri-state the way `chosen` below is: `undefined`
  // until they choose, `null` once they let a row go, a string for the key they picked.
  const [picked, setPicked] = useState<string | null | undefined>(undefined);
  // `undefined` until the reader chooses: the chooser then settles on the producer's value, the
  // direction the tool's own rule reads in, and says what that would change.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  // What the reader has put in the two fields of a range, `undefined` until they touch one:
  // the same tri-state as `picked`, `chosen` and `typed`. What the fields read is derived
  // below rather than seeded by a handler, so that a `limits` row reached by any path - by
  // hand, or opened for the reader because it is the first row that disagrees - starts on the
  // value the chooser starts on. Two empty fields are a removal, and a removal is something
  // the reader asks for, never where a row opens.
  const [edited, setEdited] = useState<{ min: string; max: string } | undefined>(undefined);
  const [changesShown, setChangesShown] = useState(false);
  // A refusal for a reason other than staleness - a type fixing this key, a kind that cannot
  // carry one, the engine's own rule - cleared whenever the reader chooses again, exactly as
  // every other choice made here.
  const [refused, setRefused] = useState<string | null>(null);
  // A refusal because a file changed on disk, the key it was refused for, and the revision it
  // happened at. A reader who chooses again straight away would send the very fingerprints that
  // were just refused, since the analysis has not caught up yet - so this is not cleared then,
  // only read through `shownRefusal`, which keeps it shown until a later revision arrives. Kept
  // with the key's own name, the way `UnitPanel` keeps it with the action it belongs to: the
  // wait is about the settlement that was refused, so another row selected in the meantime must
  // not be given its sentence, nor have its own Apply taken away by it.
  const [stale, setStale] = useState<({ key: string | undefined } & Refused) | null>(null);
  // The removal's own "Show changes", refusal and stale wait - the same three the key chooser
  // keeps for settling, kept apart because the two write paths must not answer for each other.
  const [removalShown, setRemovalShown] = useState(false);
  const [removalRefused, setRemovalRefused] = useState<string | null>(null);
  const [removalStale, setRemovalStale] = useState<Refused | null>(null);
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
  const range =
    edited ??
    (selected === undefined || variable.data === undefined
      ? { min: "", max: "" }
      : limitsOf(startingRaw(variable.data, selected)));
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
    setEdited(undefined);
    setChangesShown(false);
    setRefused(null);
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
    setEdited(next);
    setTyped(undefined);
    setRefused(null);
  };
  const apply = useMutation({
    mutationFn: () => {
      const edit =
        preview.data === undefined || selected === undefined
          ? null
          : editOf(preview.data, settleLabel(name, selected));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    // The two write paths must not answer for each other (part 6's task 9 lesson): settling a
    // key is about to change the very file a removal offer beside it reads, so starting one
    // leaves neither the other's refusal nor its open diff on screen.
    onMutate: () => {
      setRemovalRefused(null);
      setRemovalShown(false);
    },
    // The value chosen stays chosen: the panel then says there is nothing left to change. Let
    // go, it fell back on the producer's value in the declarations still on screen, which are
    // the ones the edit has just changed, and previewed undoing it. A success is a definite
    // answer, so it clears both refusals, not only the one that clears on its own.
    onSuccess: () => {
      setTyped(undefined);
      setChangesShown(false);
      setRefused(null);
      setStale(null);
    },
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so the panel never shows two different answers to the same Apply.
    onError: (error) => {
      if (error instanceof ApiError && error.code === "stale") {
        setStale({ key: selected, text: STALE, revision });
        setRefused(null);
      } else {
        setRefused(`The change was refused: ${error.message}`);
        setStale(null);
      }
    },
    // An Apply changes this variable's declarations, the units the project uses and the preview
    // it was made from, whose fingerprints the edit spent: those are asked for again, and Apply
    // stays unavailable until they answer. It changes the same file the removal offer beside it
    // reads and the component's own table lists, so a success of either write path asks for all
    // four again - only the canvas is left keyed by revision alone, moving on with the edit made.
    onSettled: () =>
      Promise.all([
        queries.invalidateQueries({ queryKey: ["variable"] }),
        queries.invalidateQueries({ queryKey: ["units"] }),
        queries.invalidateQueries({ queryKey: ["settle", name] }),
        queries.invalidateQueries({ queryKey: ["file"] }),
        queries.invalidateQueries({ queryKey: ["declarable"] }),
        queries.invalidateQueries({ queryKey: ["declaration-plan"] }),
      ]),
  });
  const remove = useMutation({
    mutationFn: () => {
      const edit =
        removal.data === undefined || file === undefined || from === undefined
          ? null
          : planEdit(removal.data, removeLabel(name, from));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    // Removing takes the whole declaration, so whatever the key chooser was showing is moot:
    // `select` is the very function letting a row go already calls, and closes the chooser the
    // same way, taking its refusal with it - the other half of the same part 6 lesson above.
    onMutate: () => select(undefined),
    // A success is a definite answer, so it clears both of this offer's own refusals too, not
    // only the one that clears on its own, mirroring `apply`'s onSuccess.
    onSuccess: () => {
      setRemovalRefused(null);
      setRemovalStale(null);
      setRemovalShown(false);
    },
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so the offer never shows two different answers to the same attempt.
    onError: (error) => {
      if (error instanceof ApiError && error.code === "stale") {
        setRemovalStale({ text: STALE, revision });
        setRemovalRefused(null);
      } else {
        setRemovalRefused(`The change was refused: ${error.message}`);
        setRemovalStale(null);
      }
    },
    // Removing changes the same four queries a settle does, the variable's declarations chief
    // among them: with none of this file's left, `GET /api/variable` answers no declarations,
    // `undeclared` above turns true, and the effect near the top closes the panel through
    // `onUndeclared` - the path the component page already names above its table, so there is
    // nothing more to write here for that.
    onSettled: () =>
      Promise.all([
        queries.invalidateQueries({ queryKey: ["variable"] }),
        queries.invalidateQueries({ queryKey: ["file"] }),
        queries.invalidateQueries({ queryKey: ["declarable"] }),
        queries.invalidateQueries({ queryKey: ["declaration-plan"] }),
      ]),
  });
  // What the removal offers, drawn the same way `UnitPanel`'s own actions are: the plan asked
  // for, why it - or applying it - was refused, and whether the plan shown is a placeholder.
  const removalOffer: Offer = {
    plan: removal.data ?? null,
    refusal:
      removalStale !== null
        ? shownRefusal(removalStale, revision)
        : (removalRefused ?? removal.error?.message ?? null),
    pending: removal.isPlaceholderData,
  };

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
      onOpenType={onOpenType}
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
        // It is the reader's own choice, so it counts as an edit of the fields.
        if (selected === "limits") setEdited(limitsOf(raw));
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
        (stale !== null && stale.key === selected ? shownRefusal(stale, revision) : null) ??
        refused ??
        (broken !== null || preview.error === null ? null : preview.error.message)
      }
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      // Left out on the project screen's own panel (`file` is `undefined` there, and so is
      // `from`, since nothing in `variable.declarations` can match a file that names none):
      // Task 7's optional prop then draws no offer at all.
      removal={
        file === undefined || from === undefined
          ? undefined
          : {
              offer: removalOffer,
              from,
              shown: removalShown,
              onShown: setRemovalShown,
              onRemove: () => remove.mutate(),
            }
      }
      busy={stopped || apply.isPending || remove.isPending}
      focus={focusPicker}
      onClose={onClose}
    />
  );
}
