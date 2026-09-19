import { Cell, Column, Row, Table, TableBody, TableHeader } from "./Table";

export default { title: "UI / Table" };

const ROWS = [
  { id: "a", name: "ValueA", unit: "%", error: false },
  { id: "b", name: "ValueB", unit: "V", error: false },
  { id: "c", name: "ValueE", unit: "Hz", error: false },
  { id: "d", name: "ValueF", unit: "degC", error: true },
];

export const Selectable = () => (
  <Table aria-label="Declarations" selectionMode="single" selectedKeys={new Set(["b"])}>
    <TableHeader>
      <Column isRowHeader>Name</Column>
      <Column>Unit</Column>
    </TableHeader>
    <TableBody items={ROWS}>
      {(row) => (
        <Row
          id={row.id}
          // A row with an error among its findings, marked as ComponentPage marks it: its class
          // keeps React Aria's own, which ui.css selects on, and adds has-error beside it.
          className={({ defaultClassName }) =>
            row.error ? `${defaultClassName} has-error` : (defaultClassName ?? "")
          }
        >
          <Cell>{row.name}</Cell>
          <Cell>{row.unit}</Cell>
        </Row>
      )}
    </TableBody>
  </Table>
);
