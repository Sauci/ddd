import { useQuery } from "@tanstack/react-query";
import type { MouseEvent } from "react";
import { useState } from "react";
import { getFile } from "../api/client";
import type { State } from "../api/types";
import { keyedFindings, leadsElsewhere, routeHref, routeOf } from "../lib/findings";
import type { ComponentFile } from "../lib/formats";
import { pointerOf, valueAt, within } from "../lib/pointer";
import { asList, asText } from "../lib/values";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { DeclarePanel } from "./DeclarePanel";
import { UndoStrip } from "./UndoStrip";
import { VariablePanel } from "./VariablePanel";

interface Props {
  file: string;
  variable: string | undefined;
  state: State | null;
  stopped: boolean;
  onVariable: (variable: string | undefined) => void;
  /** Opening the values grid of a shaped declaration - its own page, not a panel this screen
   * can show in place (spec 5.4). */
  onValues: (variable: string) => void;
  /** Following a fixed key of the open variable's panel to the type that fixes it - the
   * project's Types tab, which leaves this page: the type is the project's, not the
   * component's. */
  onOpenType: (name: string) => void;
}

/** The kinds whose definition states no `dimensions` at all and reads its own word instead - a
 * curve or a map over its axis or axes, or an axis itself. */
const SHAPED_BY_KIND = new Set(["curve", "map", "axis"]);

/** Whether this declaration's kind is one of those - a numeric table whose shape follows from
 * the axes it refers to, which the file itself cannot resolve. */
function shapedByKind(kind: string | undefined): kind is string {
  return kind !== undefined && SHAPED_BY_KIND.has(kind);
}

/** The Shape column's text for one declaration, read from the file already open rather than
 * asked of the server: `State` carries no dictionary, only `revision`, `project`, `files`,
 * `findings` and `undoable`, so there is no second source and no request per row.
 *
 * A `dimensions` on the definition is spelled the way the file spells each entry - `16`, or
 * `4 × 2` for more than one - exactly as a type member's own dimensions are (`projectTypes.ts`).
 * A curve, a map or an axis carries no `dimensions` at all, and reads its kind's own word; a
 * scalar - `dimensions` and a shaped kind both absent - is blank, `null`, and no button. */
function shapeOf(kind: string | undefined, dimensions: readonly unknown[]): string | null {
  if (dimensions.length > 0) return dimensions.map(String).join(" × ");
  return shapedByKind(kind) ? kind : null;
}

/** One component: its declarations, the panel of the one selected, and the findings in it. */
export function ComponentPage({
  file,
  variable,
  state,
  stopped,
  onVariable,
  onValues,
  onOpenType,
}: Props) {
  // A new number on every unit cell press, even a second press of the same cell, so the
  // picker's focus request always changes; null when a row selects its variable without one.
  const [focusPicker, setFocusPicker] = useState<number | null>(null);
  // The variable whose panel closed because no file declares it any longer (spec 5.5), named
  // above the table until another variable is selected or the reader leaves this page - for
  // another component's page as well.
  const [undeclared, setUndeclared] = useState<{ file: string; name: string } | null>(null);
  // The add-a-declaration form is open. The panel slot holds one panel at a time (part 6's task
  // 9 lesson): opening this one clears any selected variable, and selecting a variable - by any
  // of the table's own three ways to one - closes this one.
  const [adding, setAdding] = useState(false);
  if (undeclared !== null && undeclared.file !== file) setUndeclared(null);
  const content = useQuery({
    queryKey: ["file", file, state?.revision],
    queryFn: () => getFile(file),
    // The table stays up while this file is read again for a newer revision: swapped for
    // "Reading the file…", it lost the open panel's own draft and the scroll position on every
    // edit. Only this file's answer is kept - another component's page starts from nothing, not
    // from the last one's table - and an edit made from it carries the fingerprint it was read
    // at, which the server refuses as stale if the file has moved on.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === file ? previous : undefined,
  });

  if (content.isPending) return <p className="quiet">Reading the file…</p>;
  if (content.isError) return <Banner tone="error">{content.error.message}</Banner>;
  if (content.data.error !== null) return <Banner tone="error">{content.data.error}</Banner>;

  // Opens a variable declared in this very file without a reload - a third way to the same
  // place the row's own selection and the unit cell's button already open, so it clears the
  // same stale picker request and "no longer declared" notice they clear inline below.
  const followVariable =
    (name: string) =>
    (event: MouseEvent<HTMLAnchorElement>): void => {
      // A modified or secondary click asks the browser for a new tab or window.
      const modified = event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
      if (modified || event.button !== 0) return;
      event.preventDefault();
      setFocusPicker(null);
      setUndeclared(null);
      setAdding(false);
      onVariable(name);
    };

  const data = content.data.data;
  // The file parsed but is only checked against the schema here: it need not match
  // ComponentFile (spec 6.10), so `component` may be absent on disk though the type requires it.
  const name = (data as ComponentFile).component?.name ?? "Unnamed component";
  const findings = (state?.findings ?? []).filter((finding) => finding.file === file);
  const rows = asList(valueAt(data, "component.interface")).map((_, index) => {
    const at = pointerOf(["component", "interface", index]);
    const text = (pointer: string) => asText(valueAt(data, `${at}.${pointer}`));
    const kind = text("definition.kind");
    const datatype = text("definition.datatype");
    const dimensions = asList(valueAt(data, `${at}.definition.dimensions`));
    return {
      id: at,
      name: text("definition.name") ?? `declaration ${index + 1}`,
      scope: text("scope"),
      kind,
      type: datatype ?? text("definition.typename"),
      unit: text("definition.unit") ?? "",
      shape: shapeOf(kind, dimensions),
      // The shape is offered as a button only where the grid can draw what it opens, and shown
      // as plain text otherwise: a button that refused the moment it was pressed would be a
      // button that lies (spec 5.1). A curve, a map or an axis is a numeric table whatever type
      // it names - measured, a curve naming a scalar type resolves exactly as one stating its
      // own storage does - so its kind alone is enough. Anything else has to state both a
      // `dimensions` and a `datatype` of its own: `dimensions` beside a `typename` is a
      // structured declaration, which `DataDictionary.objects` does not hold at all, so the
      // grid would answer that the project declares no such object. A structure cannot be a
      // numeric table, which is why every `typename` declaration of examples/ is a measurement
      // or a parameter. More dimensions than two is more than a grid draws, whichever way in.
      // A text init in this very file is text and not a grid; a consumer's declaration cannot
      // see its producer's init, so a text one elsewhere is offered anyway, and the grid it
      // opens says so itself (`ValuesGridView`, `reply.stated`).
      offered:
        typeof valueAt(data, `${at}.definition.init`) !== "string" &&
        dimensions.length <= 2 &&
        (shapedByKind(kind) || (dimensions.length > 0 && datatype !== undefined)),
      own: findings.filter((finding) => within(finding.pointer, at)),
    };
  });
  const selected = new Set(rows.filter((row) => row.name === variable).map((row) => row.id));

  return (
    <section className={variable === undefined && !adding ? undefined : "with-panel"}>
      <div>
        <div className="heading">
          <h1>{name}</h1>
          <UndoStrip state={state} stopped={stopped} />
          <Button
            variant="secondary"
            isDisabled={stopped}
            onPress={() => {
              setAdding(true);
              onVariable(undefined);
            }}
          >
            Add a declaration
          </Button>
        </div>
        {undeclared !== null && (
          <Banner tone="warning">
            {undeclared.name} is no longer declared in the open project.
          </Banner>
        )}
        <Table
          aria-label={`Declarations of ${name}`}
          selectionMode="single"
          selectedKeys={selected}
          onSelectionChange={(keys) => {
            const key = keys === "all" ? undefined : [...keys][0];
            setFocusPicker(null);
            setUndeclared(null);
            setAdding(false);
            onVariable(rows.find((row) => row.id === key)?.name);
          }}
        >
          <TableHeader>
            <Column>Scope</Column>
            <Column isRowHeader>Name</Column>
            <Column>Kind</Column>
            <Column>Type</Column>
            <Column>Shape</Column>
            <Column>Unit</Column>
            <Column>Findings</Column>
          </TableHeader>
          <TableBody items={rows}>
            {(row) => (
              <Row
                id={row.id}
                className={({ defaultClassName }) =>
                  row.own.some((finding) => finding.severity === "error")
                    ? `${defaultClassName} has-error`
                    : (defaultClassName ?? "")
                }
              >
                <Cell>{row.scope}</Cell>
                <Cell>{row.name}</Cell>
                <Cell>{row.kind}</Cell>
                <Cell>{row.type}</Cell>
                <Cell>
                  {row.shape !== null &&
                    (row.offered ? (
                      <Button
                        variant="link"
                        aria-label={`Show the values of ${row.name}`}
                        isDisabled={stopped}
                        onPress={() => onValues(row.name)}
                      >
                        {row.shape}
                      </Button>
                    ) : (
                      row.shape
                    ))}
                </Cell>
                <Cell>
                  <Button
                    variant="link"
                    aria-label={`Set the unit of ${row.name}`}
                    isDisabled={stopped}
                    onPress={() => {
                      setFocusPicker((request) => (request ?? 0) + 1);
                      setUndeclared(null);
                      setAdding(false);
                      onVariable(row.name);
                    }}
                  >
                    {row.unit === "" ? <span className="quiet">none</span> : row.unit}
                  </Button>
                </Cell>
                <Cell>
                  {keyedFindings(row.own).map(([finding, key]) => (
                    <Chip key={key} tone={finding.severity === "error" ? "error" : "warning"}>
                      {finding.check}
                    </Chip>
                  ))}
                </Cell>
              </Row>
            )}
          </TableBody>
        </Table>
        <h2>Findings in this component</h2>
        {findings.length === 0 ? (
          <p className="quiet">None.</p>
        ) : (
          <ul className="findings">
            {keyedFindings(findings).map(([finding, key]) => {
              const href = leadsElsewhere(finding, file) ? routeHref(finding) : null;
              const route = href === null ? null : routeOf(finding);
              // A variable named by this very file's own route opens in place via
              // `followVariable`; a unit's route leaves the component page, which nothing here
              // can do in place, so it stays a plain address the browser follows. A values route
              // also leaves this page, for the grid rather than the panel `onVariable` alone can
              // open - `followVariable` cannot say `view=values`, so it stays a plain address
              // too, the same as a unit's.
              const inThisFile =
                route !== null &&
                route.page === "component" &&
                route.variable !== undefined &&
                !("view" in route)
                  ? route.variable
                  : null;
              const onClick = inThisFile === null ? undefined : followVariable(inThisFile);
              return (
                <li key={key} className={finding.severity}>
                  <span className="check">{finding.check}</span>{" "}
                  {href === null ? (
                    <span className="message">{finding.message}</span>
                  ) : (
                    <a className="button link" href={href} onClick={onClick}>
                      {finding.message}
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {variable !== undefined && (
        <VariablePanel
          key={variable}
          name={variable}
          file={file}
          revision={state?.revision}
          stopped={stopped}
          focusPicker={focusPicker}
          onClose={() => onVariable(undefined)}
          onUndeclared={() => {
            setUndeclared({ file, name: variable });
            onVariable(undefined);
          }}
          onOpenType={onOpenType}
        />
      )}
      {adding && (
        <DeclarePanel
          file={file}
          component={name}
          revision={state?.revision}
          stopped={stopped}
          onClose={() => setAdding(false)}
          onDeclared={(declared) => {
            setAdding(false);
            setUndeclared(null);
            onVariable(declared);
          }}
        />
      )}
    </section>
  );
}
