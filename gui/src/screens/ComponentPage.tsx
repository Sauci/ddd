import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getFile } from "../api/client";
import type { State } from "../api/types";
import { keyedFindings } from "../lib/findings";
import type { ComponentFile } from "../lib/formats";
import { pointerOf, valueAt, within } from "../lib/pointer";
import { asList, asText } from "../lib/values";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { VariablePanel } from "./VariablePanel";

interface Props {
  file: string;
  variable: string | undefined;
  state: State | null;
  stopped: boolean;
  onVariable: (variable: string | undefined) => void;
}

/** One component: its declarations, the panel of the one selected, and the findings in it. */
export function ComponentPage({ file, variable, state, stopped, onVariable }: Props) {
  // A new number on every unit cell press, even a second press of the same cell, so the
  // picker's focus request always changes; null when a row selects its variable without one.
  const [focusPicker, setFocusPicker] = useState<number | null>(null);
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

  const data = content.data.data;
  // The file parsed but is only checked against the schema here: it need not match
  // ComponentFile (spec 6.10), so `component` may be absent on disk though the type requires it.
  const name = (data as ComponentFile).component?.name ?? "Unnamed component";
  const findings = (state?.findings ?? []).filter((finding) => finding.file === file);
  const rows = asList(valueAt(data, "component.interface")).map((_, index) => {
    const at = pointerOf(["component", "interface", index]);
    const text = (pointer: string) => asText(valueAt(data, `${at}.${pointer}`));
    return {
      id: at,
      name: text("definition.name") ?? `declaration ${index + 1}`,
      scope: text("scope"),
      kind: text("definition.kind"),
      type: text("definition.datatype") ?? text("definition.typename"),
      unit: text("definition.unit") ?? "",
      own: findings.filter((finding) => within(finding.pointer, at)),
    };
  });
  const selected = new Set(rows.filter((row) => row.name === variable).map((row) => row.id));

  return (
    <section className={variable === undefined ? undefined : "with-panel"}>
      <div>
        <h1>{name}</h1>
        <Table
          aria-label={`Declarations of ${name}`}
          selectionMode="single"
          selectedKeys={selected}
          onSelectionChange={(keys) => {
            const key = keys === "all" ? undefined : [...keys][0];
            setFocusPicker(null);
            onVariable(rows.find((row) => row.id === key)?.name);
          }}
        >
          <TableHeader>
            <Column>Scope</Column>
            <Column isRowHeader>Name</Column>
            <Column>Kind</Column>
            <Column>Type</Column>
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
                  <Button
                    variant="link"
                    aria-label={`Set the unit of ${row.name}`}
                    isDisabled={stopped}
                    onPress={() => {
                      setFocusPicker((request) => (request ?? 0) + 1);
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
            {keyedFindings(findings).map(([finding, key]) => (
              <li key={key} className={finding.severity}>
                <span className="check">{finding.check}</span>{" "}
                <span className="message">{finding.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {variable !== undefined && (
        <VariablePanel
          key={variable}
          name={variable}
          revision={state?.revision}
          stopped={stopped}
          focusPicker={focusPicker}
          onClose={() => onVariable(undefined)}
        />
      )}
    </section>
  );
}
