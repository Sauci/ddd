import { Cell, Column, Row, Table, TableBody, TableHeader } from "./Table";

export default { title: "UI / Table" };

const ROWS = [
  { id: "a", name: "ValueA", unit: "%" },
  { id: "b", name: "ValueB", unit: "V" },
  { id: "c", name: "ValueE", unit: "Hz" },
];

export const Selectable = () => (
  <Table aria-label="Declarations" selectionMode="single" selectedKeys={new Set(["b"])}>
    <TableHeader>
      <Column isRowHeader>Name</Column>
      <Column>Unit</Column>
    </TableHeader>
    <TableBody items={ROWS}>
      {(row) => (
        <Row id={row.id}>
          <Cell>{row.name}</Cell>
          <Cell>{row.unit}</Cell>
        </Row>
      )}
    </TableBody>
  </Table>
);
