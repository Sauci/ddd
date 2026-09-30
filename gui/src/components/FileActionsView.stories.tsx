import { type ReactNode, useState } from "react";
import type { FilesPlanReply, FilesReply, SourceFile } from "../api/types";
import { fileRemoval, rowsOf } from "../lib/files";
import {
  ADD_BRINGING,
  ADDABLE_FILES,
  ADDABLE_SOURCES,
  ADDED_BY_A_PATTERN,
  COMPONENT_NAME_TAKEN,
  CREATE_COMPONENT,
  CREATE_CONSTANTS,
  CREATE_FIRST_UNITS,
  CREATE_RASTERS,
  CREATE_SECTIONS,
  CREATE_TYPES,
  CREATE_UNITS,
  FIRST_UNITS_FILES,
  FIRST_UNITS_SOURCES,
  KEPT_A,
  KEPT_FILES,
  KEPT_SOURCES,
  PROJECT_FILES,
  PROJECT_SOURCE_FILES,
  READER_BROKEN,
  READER_FILES,
  READER_SOURCES,
  REMOVE_KEPT,
  REMOVE_LEAVES_AN_ERROR,
  REMOVE_UNJUDGED,
  VOCABULARY_CONSTANTS,
} from "../stories/fixtures";
import { AddFileView, FileActionsView, NewFileView, RemoveFileView } from "./FileActionsView";
import { FilesTableView } from "./FilesTableView";

export default { title: "Components / FileActionsView" };

interface Scene {
  /** `GET /api/files`' answer for the project the story is about: examples/vocabulary's own list
   * unless the scenario is a constructed tree (fixtures.ts says which, and which test builds it). */
  reply?: FilesReply;
  /** `State.files`' own entries for the files that list names. */
  files?: readonly SourceFile[];
  /** The plan the server answered, or nothing where it refused. */
  plan?: FilesPlanReply;
  /** The server's refusal, in its words - a sentence tests/test_gui_api.py pins whole. */
  refusal?: string;
  /** Whether Show changes starts open. */
  shown?: boolean;
}

/** The Files tab laid out as FilesPage.tsx lays it out: the two actions above the table, and the
 * panel beside it - the row the panel is about, where it is one, marked in the table. */
function Tab({
  reply,
  files,
  selected,
  children,
}: {
  reply: FilesReply;
  files: readonly SourceFile[];
  selected?: string;
  children: ReactNode;
}) {
  return (
    <>
      <FileActionsView onNewFile={() => undefined} onAddFile={() => undefined} />
      <div className="with-panel">
        <div>
          <FilesTableView
            reply={reply}
            files={files}
            selected={selected}
            onSelect={() => undefined}
          />
        </div>
        {children}
      </div>
    </>
  );
}

/** New file's form over one scenario, holding its own fields as FilesPage.tsx's `NewFile` keeps
 * them. */
function NewFile({
  reply = PROJECT_FILES,
  files = PROJECT_SOURCE_FILES,
  kind,
  name,
  component = "",
  plan,
  refusal,
  shown = false,
}: Scene & { kind: string; name: string; component?: string }) {
  const [typedKind, setKind] = useState(kind);
  const [typedName, setName] = useState(name);
  const [typedComponent, setComponent] = useState(component);
  const [changesShown, setChangesShown] = useState(shown);
  return (
    <Tab reply={reply} files={files}>
      <NewFileView
        project={reply.project}
        creatable={reply.creatable}
        kind={typedKind}
        onKind={setKind}
        name={typedName}
        onName={setName}
        component={typedComponent}
        onComponent={setComponent}
        offer={{ plan: plan ?? null, refusal: refusal ?? null }}
        changesShown={changesShown}
        onChangesShown={setChangesShown}
        onApply={() => undefined}
        busy={false}
        onClose={() => undefined}
      />
    </Tab>
  );
}

/** Add's form over one scenario, holding its path as FilesPage.tsx's `AddFile` keeps it. */
function AddFile({
  reply = PROJECT_FILES,
  files = PROJECT_SOURCE_FILES,
  path,
  plan,
  refusal,
  shown = false,
}: Scene & { path: string }) {
  const [typed, setTyped] = useState(path);
  const [changesShown, setChangesShown] = useState(shown);
  return (
    <Tab reply={reply} files={files}>
      <AddFileView
        project={reply.project}
        path={typed}
        onPath={setTyped}
        offer={{ plan: plan ?? null, refusal: refusal ?? null }}
        changesShown={changesShown}
        onChangesShown={setChangesShown}
        onApply={() => undefined}
        busy={false}
        onClose={() => undefined}
      />
    </Tab>
  );
}

/** A row's Remove panel over one scenario: the row the address selects, found by `fileRemoval`
 * exactly as FilesPage.tsx finds it. */
function Remove({
  reply = PROJECT_FILES,
  files = PROJECT_SOURCE_FILES,
  selected,
  plan,
  refusal,
  shown = false,
}: Scene & { selected: string }) {
  const [changesShown, setChangesShown] = useState(shown);
  const removal = fileRemoval(rowsOf(reply, files), selected, reply.project);
  return (
    <Tab reply={reply} files={files} selected={selected}>
      {removal !== null && (
        <RemoveFileView
          removal={removal}
          project={reply.project}
          offer={{ plan: plan ?? null, refusal: refusal ?? null }}
          changesShown={changesShown}
          onChangesShown={setChangesShown}
          onApply={() => undefined}
          busy={false}
          onClose={() => undefined}
        />
      )}
    </Tab>
  );
}

/** A component, over examples/vocabulary: the Component name field drawn beside the file's own,
 * since a component takes both; the plan creates valve.ddd.json declaring `Valve` with an empty
 * interface and appends it to the includes - Show changes open on both files. */
export const NewComponentFile = () => (
  <NewFile kind="component" name="valve" component="Valve" plan={CREATE_COMPONENT} shown />
);

/** A types file, sizes.ddd.json, declaring nothing: no Component name field. */
export const NewTypesFile = () => <NewFile kind="types" name="sizes" plan={CREATE_TYPES} shown />;

/** A second units file, more_units.ddd.json, created declaring nothing: examples/vocabulary has
 * units.ddd.json already, so the project is opted in and nothing it states is listed again. */
export const NewUnitsFile = () => (
  <NewFile kind="units" name="more_units" plan={CREATE_UNITS} shown />
);

/** A constants file, limits.ddd.json, declaring nothing - the one plan of the six a test pins
 * whole. */
export const NewConstantsFile = () => (
  <NewFile kind="constants" name="limits" plan={CREATE_CONSTANTS} shown />
);

/** A sections file, memory.ddd.json, declaring nothing. */
export const NewSectionsFile = () => (
  <NewFile kind="sections" name="memory" plan={CREATE_SECTIONS} shown />
);

/** A rasters file, tasks.ddd.json, declaring nothing. */
export const NewRastersFile = () => (
  <NewFile kind="rasters" name="tasks" plan={CREATE_RASTERS} shown />
);

/** A first units file (constructed, fixtures.ts says which test's tree): the project has no units
 * file anywhere, so the one created lists the two units its component states, `%` and `rpm`, each
 * with an empty description - created empty, it would have made both an `unknown-unit`. */
export const AFirstUnitsFileListsItsUnits = () => (
  <NewFile
    reply={FIRST_UNITS_FILES}
    files={FIRST_UNITS_SOURCES}
    kind="units"
    name="units"
    plan={CREATE_FIRST_UNITS}
    shown
  />
);

/** New file refused as it is typed, the component's name being pump.ddd.json's own: the server's
 * sentence, and no plan to apply. */
export const NewFileRefused = () => (
  <NewFile kind="component" name="motor" component="Pump" refusal={COMPONENT_NAME_TAKEN} />
);

/** Add bringing an error (constructed: ADDABLE): b.ddd.json reads 'Torque', which nothing writes,
 * so its preview lists the `missing-producer` it would bring, as the server lists it - and offers
 * Apply all the same, since adding informs rather than refuses. */
export const AddBringingAnError = () => (
  <AddFile reply={ADDABLE_FILES} files={ADDABLE_SOURCES} path="b.ddd.json" plan={ADD_BRINGING} />
);

/** Add refused (constructed: ADDABLE): lib/l.ddd.json is in the project already, the pattern
 * lib/*.ddd.json bringing it in - its row indented beneath the pattern's in the table. */
export const AddRefusedAsAPatternsFile = () => (
  <AddFile
    reply={ADDABLE_FILES}
    files={ADDABLE_SOURCES}
    path="lib/l.ddd.json"
    refusal={ADDED_BY_A_PATTERN}
  />
);

/** Remove refused, over examples/vocabulary: constants.ddd.json's row selected, and the server
 * naming the error the project would be left with - TREND_SAMPLES, which pump.ddd.json's
 * PressureTrend is dimensioned by. No button: there is no plan to apply. */
export const RemoveRefusedForTheErrorItWouldLeave = () => (
  <Remove selected={VOCABULARY_CONSTANTS} refusal={REMOVE_LEAVES_AN_ERROR} />
);

/** Remove unjudged (constructed: READER_OF_A_BROKEN_WRITER): the half-saved lib/b.ddd.json did not
 * load, so the project's analysis did not run to its end; removing it is allowed, and the server's
 * own sentence says why nothing was judged. */
export const RemoveUnjudgedWhereAFileDidNotLoad = () => (
  <Remove
    reply={READER_FILES}
    files={READER_SOURCES}
    selected={READER_BROKEN}
    plan={REMOVE_UNJUDGED}
  />
);

/** Remove, a pattern keeping the file in (constructed): a.ddd.json is both a literal entry and the
 * one match of `*.ddd.json`, both rows marked; removing it takes out the literal line alone - Show
 * changes open on it - and a line says the pattern keeps the file in the project all the same: of
 * the three values only a files plan carries, `kept_by` is the one the page puts into words of its
 * own, and this picture pins that wording as `previewOf`'s tests pin its text. */
export const RemoveKeptInByAPattern = () => (
  <Remove reply={KEPT_FILES} files={KEPT_SOURCES} selected={KEPT_A} plan={REMOVE_KEPT} shown />
);
