import { useState } from "react";
import { DimensionsField } from "./DimensionsField";

export default { title: "Components / DimensionsField" };

export function OneDimensionNotYetStated() {
  const [rows, setRows] = useState<string[]>([]);
  return (
    <DimensionsField rows={rows} constants={[]} owner="BlockB" busy={false} onRows={setRows} />
  );
}

export function TwoDimensionsStated() {
  const [rows, setRows] = useState(["4", "8"]);
  return (
    <DimensionsField rows={rows} constants={[]} owner="BlockB" busy={false} onRows={setRows} />
  );
}

export function AConstantAmongThem() {
  const [rows, setRows] = useState(["PRESSURE_CELLS", "4"]);
  return (
    <DimensionsField
      rows={rows}
      constants={["PRESSURE_CELLS", "SENSOR_COUNT"]}
      owner="BlockB"
      busy={false}
      onRows={setRows}
    />
  );
}
