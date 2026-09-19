import type { Finding, SettleReply, UnitsReply, VariableReply } from "../api/types";

// Paths as the spec's own examples spell them (docs/superpowers/specs/2026-09-18-gui-units-
// design.md, 4.3): absolute and posix, on a Windows checkout.
const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";
const CONTROLLER = "C:/work/demo/components/controller.ddd.json";
const USER_INTERFACE = "C:/work/demo/components/user_interface.ddd.json";

const MISMATCH: Finding = {
  file: CONTROLLER,
  check: "definition-mismatch",
  severity: "error",
  message: "Controller states rpm, SensorHub %",
  pointer: "component.interface[0].definition.unit",
  notes: [],
};

/** ValueA as the mockups show it: SensorHub produces %, Controller reads rpm, one finding. */
export const DISAGREEING: VariableReply = {
  revision: 7,
  name: "ValueA",
  declarations: [
    {
      path: SENSOR_HUB,
      pointer: "component.interface[2].definition",
      component: "SensorHub",
      role: "produces",
      stated: { kind: '"measurement"', datatype: '"uint8"', unit: '"%"' },
      type: null,
      fixed: {},
    },
    {
      path: CONTROLLER,
      pointer: "component.interface[0].definition",
      component: "Controller",
      role: "reads",
      stated: { kind: '"measurement"', datatype: '"uint8"', unit: '"rpm"' },
      type: null,
      fixed: {},
    },
    {
      path: USER_INTERFACE,
      pointer: "component.interface[0].definition",
      component: "UserInterface",
      role: "reads",
      stated: { kind: '"measurement"', datatype: '"uint8"', unit: '"%"' },
      type: null,
      fixed: {},
    },
  ],
  findings: [MISMATCH],
};

/** The same declarations settled: Controller reads % too, and the disagreement is gone. */
export const AGREEING: VariableReply = {
  ...DISAGREEING,
  declarations: DISAGREEING.declarations.map((declaration) =>
    declaration.component === "Controller"
      ? { ...declaration, stated: { ...declaration.stated, unit: '"%"' } }
      : declaration,
  ),
  findings: [],
};

/** ValueA declared by a type that fixes its unit: SensorHub names Speed_t and states no unit. */
export const FIXED_BY_TYPE: VariableReply = {
  revision: 7,
  name: "ValueA",
  declarations: [
    {
      path: SENSOR_HUB,
      pointer: "component.interface[2].definition",
      component: "SensorHub",
      role: "produces",
      stated: { kind: '"measurement"' },
      type: "Speed_t",
      fixed: { unit: '"rpm"' },
    },
  ],
  findings: [],
};

/** A row of the Units tab, which the variable panel does not read: a unit variables state. */
function row(
  unit: string,
  variables: number,
  description: string | null = null,
  files: string[] = [],
): UnitsReply["units"][number] {
  return { unit, description, files, variables, types: 0, members: 0, findings: 0 };
}

/** A project with no units vocabulary: the picker's "Other units in this project" list. */
export const FREE_UNITS: UnitsReply = {
  revision: 7,
  vocabulary: null,
  used: [
    { unit: "Hz", variables: 4 },
    { unit: "%", variables: 3 },
    { unit: "V", variables: 3 },
    { unit: "degC", variables: 1 },
    { unit: "rpm", variables: 1 },
  ],
  units: [row("%", 3), row("Hz", 4), row("V", 3), row("degC", 1), row("rpm", 1)],
  adoptable: 5,
};

const UNITS_FILE = "C:/work/demo/units.ddd.json";

/** A project's declared vocabulary, described, with how many variables use each. */
export const VOCABULARY: UnitsReply = {
  revision: 7,
  vocabulary: [
    { unit: "rpm", description: "rotational speed, revolutions per minute" },
    { unit: "Nm", description: "torque, newton metre" },
    { unit: "degC", description: "temperature" },
    { unit: "kPa", description: "pressure" },
  ],
  used: [{ unit: "rpm", variables: 1 }],
  units: [
    row("Nm", 0, "torque, newton metre", [UNITS_FILE]),
    row("degC", 0, "temperature", [UNITS_FILE]),
    row("kPa", 0, "pressure", [UNITS_FILE]),
    row("rpm", 1, "rotational speed, revolutions per minute", [UNITS_FILE]),
  ],
  adoptable: null,
};

/** The one-hunk preview of chosen-design.html's "Show changes": controller.ddd.json, line 14. */
export const ONE_FILE: SettleReply = {
  revision: 7,
  changes: [
    {
      file: CONTROLLER,
      fingerprint: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      operations: [{ op: "set", pointer: "component.interface[0].definition.unit", raw: '"%"' }],
      hunks: [
        { line: 14, before: ['          "unit": "rpm",'], after: ['          "unit": "%",'] },
      ],
    },
  ],
};

/** Every declaration already agrees: nothing to change. */
export const NOTHING: SettleReply = { revision: 7, changes: [] };
