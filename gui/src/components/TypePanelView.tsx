import type { PlanReply, TypeReply, TypeUse, UnitsReply } from "../api/types";
import { distinctFindings, keyedFindings, routeOf } from "../lib/findings";
import { keyRowsOfType, memberRows } from "../lib/projectTypes";
import type { Route } from "../lib/route";
import { baseName, consequence, shownChanges, textOf } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { Changes } from "./Changes";
import { KeyChooser } from "./KeyChooser";

export interface TypePanelViewProps {
  type: TypeReply;
  units: UnitsReply;
  /** Which key's chooser is open, or `undefined` while none is. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
  /** Everything the chooser needs, passed through as the variable panel passes it. */
  typed: string;
  onTyped: (text: string) => void;
  onChosen: (raw: string | null) => void;
  onPickerClosed: () => void;
  range: { min: string; max: string };
  onRange: (range: { min: string; max: string }) => void;
  /** What the reader types into the Description field, and into Rename. */
  description: string;
  onDescription: (text: string) => void;
  renameTo: string | null;
  onRenameTo: (to: string | null) => void;
  /** The preview of whichever change is pending, or `null` while there is none. */
  preview: PlanReply | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  /** Following a use or a finding, without a reload. */
  onOpen: (route: Route) => void;
  refusal: string | null;
  busy: boolean;
  onClose: () => void;
}

/** What a kind is called on the page: the file says `struct`, a reader reads "structure" - the
 * same three words `lib/projectTypes.ts` keeps for the tab's own table, kept here too since this
 * panel reads one type alone and has no reason to import a table row's shaping for one field. */
const KIND_WORDS: Record<string, string> = {
  scalar: "scalar",
  struct: "structure",
  external: "external",
};

/** One type's panel (spec 5.2), drawn from what the api answered: a picture of its props. */
export function TypePanelView(props: TypePanelViewProps) {
  const { type, units, selected, preview, refusal, renameTo, busy } = props;
  const keyRows = keyRowsOfType(type);
  const selectedRow = keyRows.find((row) => row.key === selected);
  const kindWord = KIND_WORDS[type.kind] ?? "unknown";
  // An external type fixes nothing a chooser edits (`keys` is empty, like a structure's) but its
  // header is the one fact that makes it external at all, so the meta line carries it - the same
  // place `unitMeta`/`typesTitle` already pack a quick fact onto the line under a title.
  const meta =
    type.header === null
      ? `${kindWord} · ${baseName(type.file)}`
      : `${kindWord} · ${baseName(type.file)} · ${type.header}`;
  return (
    <Panel title={type.name} meta={meta} onClose={props.onClose}>
      <section className="panel-offer" aria-label="Description">
        <label className="panel-field">
          Description
          <input
            type="text"
            value={props.description}
            disabled={busy}
            onChange={(event) => props.onDescription(event.target.value)}
          />
        </label>
      </section>
      {keyRows.length > 0 && (
        <>
          <h3 className="panel-heading">What it fixes</h3>
          <Table
            aria-label={`What ${type.name} fixes`}
            selectionMode="single"
            selectedKeys={new Set(selected === undefined ? [] : [selected])}
            onSelectionChange={(keys) => {
              const key = keys === "all" ? undefined : [...keys][0];
              props.onSelect(typeof key === "string" ? key : undefined);
            }}
          >
            <TableHeader>
              <Column isRowHeader>Key</Column>
              <Column>What it fixes</Column>
            </TableHeader>
            <TableBody items={keyRows}>
              {(row) => (
                <Row id={row.key}>
                  <Cell>{row.label}</Cell>
                  <Cell>{row.text}</Cell>
                </Row>
              )}
            </TableBody>
          </Table>
          {selectedRow !== undefined && (
            <KeyChooser
              // A fresh instance per key selected, so the field the reader just opened always
              // takes the focus - hardcoding `focus`/`pickerTrigger` below would otherwise never
              // change and so never ask again for a row picked after the first.
              key={selectedRow.key}
              offer={selectedRow.offer}
              owner={type.name}
              inPlay={new Map([[unitOf(type), []]])}
              keyName={selectedRow.key}
              units={units}
              typed={props.typed}
              narrow=""
              onTyped={props.onTyped}
              onChosen={props.onChosen}
              onPickerClosed={props.onPickerClosed}
              range={props.range}
              onRange={props.onRange}
              note={undefined}
              busy={busy}
              focus={1}
              pickerTrigger="focus"
            />
          )}
        </>
      )}
      <section className="panel-offer" aria-label="Rename">
        <label className="panel-field">
          {`Rename ${type.name} to`}
          <input
            type="text"
            value={renameTo ?? type.name}
            disabled={busy}
            onChange={(event) => {
              const text = event.target.value;
              props.onRenameTo(text === type.name ? null : text);
            }}
          />
        </label>
        <p className="rename-note">Only the name changes; what the type fixes stays as it is.</p>
      </section>
      {refusal !== null ? (
        <p className="panel-refusal" role="status">
          {refusal}
        </p>
      ) : (
        // As the variable panel's own consequence line stays with `selected !== undefined`: a
        // stale preview says nothing once nothing is pending, key chosen or rename typed alike.
        (selected !== undefined || renameTo !== null) &&
        preview !== null && <p className="consequence">{consequence(preview.changes)}</p>
      )}
      {refusal === null &&
        (selected !== undefined || renameTo !== null) &&
        preview !== null &&
        preview.changes.length > 0 && (
          <>
            {props.changesShown && <Changes changes={shownChanges(preview.changes)} />}
            <div className="panel-actions">
              <Button variant="link" onPress={() => props.onChangesShown(!props.changesShown)}>
                {props.changesShown ? "Hide changes" : "Show changes"}
              </Button>
              <Button variant="primary" isDisabled={busy} onPress={props.onApply}>
                Apply to {preview.changes.length} file{preview.changes.length === 1 ? "" : "s"}
              </Button>
            </div>
          </>
        )}
      <h3 className="panel-heading">Where it is used</h3>
      {type.uses.length === 0 ? (
        <p className="quiet">Nothing in the project uses {type.name}.</p>
      ) : (
        <table className="panel-declarations">
          <thead>
            <tr>
              <th scope="col">Where</th>
              <th scope="col">File</th>
              <th scope="col">What</th>
            </tr>
          </thead>
          <tbody>
            {type.uses.map((use) => (
              <tr key={`${use.path} ${use.pointer}`}>
                <td>
                  <Button variant="link" onPress={() => props.onOpen(routeOfUse(use))}>
                    {use.name}
                  </Button>
                </td>
                <td className="quiet">{baseName(use.path)}</td>
                <td>{whatOf(use)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {type.kind === "struct" && (
        <>
          <h3 className="panel-heading">Members</h3>
          <table className="panel-declarations">
            <thead>
              <tr>
                <th scope="col">Member</th>
                <th scope="col">Holds</th>
                <th scope="col">Type</th>
                <th scope="col">Unit</th>
                <th scope="col">Bits</th>
                <th scope="col">Dimensions</th>
              </tr>
            </thead>
            <tbody>
              {memberRows(type).map((row, at) => {
                const member = type.members[at];
                const typename = member?.typename ?? null;
                return (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td>{row.member}</td>
                    <td>
                      {typename === null ? (
                        row.type
                      ) : (
                        <Button
                          variant="link"
                          onPress={() =>
                            props.onOpen({ page: "project", view: "types", type: typename })
                          }
                        >
                          {row.type}
                        </Button>
                      )}
                    </td>
                    <td>{row.unit}</td>
                    <td>{row.bits}</td>
                    <td>{row.dimensions}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
      {type.findings.length > 0 && (
        <ul className="panel-findings">
          {keyedFindings(distinctFindings(type.findings)).map(([finding, key]) => {
            const route = routeOf(finding);
            return (
              <li key={key}>
                <Chip tone={finding.severity === "error" ? "error" : "warning"}>
                  {finding.check}
                </Chip>{" "}
                {route === null ? (
                  <span className="quiet">{finding.message}</span>
                ) : (
                  <Button variant="link" onPress={() => props.onOpen(route)}>
                    {finding.message}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

/** What a use's row says under What: the component and role for a variable's declaration, the
 * one word for a structure member - `type.members[i].member` already says which kind of member,
 * so this is only ever the noun, never "value" or "bits". */
function whatOf(use: TypeUse): string {
  return use.kind === "member" ? "member" : `${use.component ?? ""} · ${use.role ?? ""}`;
}

/** Where a use's row leads: a variable's panel on its component's page, or - a member's `name`
 * always being `"<Type>.<member>"` (the api's own `TypeUse.name` doc) - the type holding it. */
function routeOfUse(use: TypeUse): Route {
  if (use.kind === "variable") {
    return { page: "component", file: use.path, variable: use.name };
  }
  const dot = use.name.indexOf(".");
  return { page: "project", view: "types", type: dot === -1 ? use.name : use.name.slice(0, dot) };
}

/** The one unit a type states, for the key chooser's `inPlay` - the picker's first section then
 * reads exactly as a variable's, whose declarations state it instead. */
function unitOf(type: TypeReply): string | null {
  const offer = type.keys.find((entry) => entry.key === "unit");
  return textOf(offer?.values[0]?.raw);
}
