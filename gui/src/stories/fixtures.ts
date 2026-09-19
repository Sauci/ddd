import type {
  Finding,
  PlanReply,
  ProjectUnit,
  SettleReply,
  UnitReply,
  UnitsReply,
  VariableReply,
} from "../api/types";

// Paths as the spec's own examples spell them (docs/superpowers/specs/2026-09-18-gui-units-
// design.md, 4.3): absolute and posix, on a Windows checkout.
const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";
const CONTROLLER = "C:/work/demo/components/controller.ddd.json";
const USER_INTERFACE = "C:/work/demo/components/user_interface.ddd.json";
const PUMP = "C:/work/demo/components/pump.ddd.json";
const TYPES = "C:/work/demo/types.ddd.json";
const DEMO = "C:/work/demo/demo.ddd.json";

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

// The Units tab of part 2's mockups (docs/superpowers/specs/2026-09-19-gui-units-project/), whose
// DemoDevice states nine units, two of them outside its vocabulary.

/** RPM, outside the vocabulary: Controller reads EngineSpeed in it and the type Speed_t states
 * it, each with an `unknown-unit` finding. */
export const UNKNOWN_RPM: ProjectUnit = { ...row("RPM", 1), types: 1, findings: 2 };

/** rpm, which the vocabulary lists and describes, stated by two variables. */
export const LISTED_RPM = row("rpm", 2, "rotational speed, revolutions per minute", [UNITS_FILE]);

/** kPa, which the vocabulary lists and nothing states. */
export const UNUSED_KPA = row("kPa", 0, "pressure", [UNITS_FILE]);

/** The mockups' project: its vocabulary, and the nine units it states or lists. */
export const PROJECT_UNITS: UnitsReply = {
  revision: 7,
  vocabulary: [
    { unit: "%", description: "percentage" },
    { unit: "Hz", description: "frequency" },
    { unit: "rpm", description: "rotational speed, revolutions per minute" },
    { unit: "V", description: "voltage" },
    { unit: "degC", description: "temperature" },
    { unit: "ms", description: "time" },
    { unit: "kPa", description: "pressure" },
  ],
  used: [
    { unit: "%", variables: 4 },
    { unit: "Hz", variables: 3 },
    { unit: "V", variables: 2 },
    { unit: "degC", variables: 2 },
    { unit: "rpm", variables: 2 },
    { unit: "RPM", variables: 1 },
    { unit: "ms", variables: 1 },
    { unit: "°C", variables: 1 },
  ],
  units: [
    UNKNOWN_RPM,
    { ...row("°C", 1), findings: 1 },
    row("%", 4, "percentage", [UNITS_FILE]),
    row("Hz", 3, "frequency", [UNITS_FILE]),
    LISTED_RPM,
    row("V", 2, "voltage", [UNITS_FILE]),
    row("degC", 2, "temperature", [UNITS_FILE]),
    row("ms", 1, "time", [UNITS_FILE]),
    UNUSED_KPA,
  ],
  adoptable: null,
};

/** The same project before it had a units file: its eight units in use, none of them checked. */
export const UNADOPTED_UNITS: UnitsReply = {
  revision: 7,
  vocabulary: null,
  used: PROJECT_UNITS.used,
  units: PROJECT_UNITS.units
    .filter((unit) => unit !== UNUSED_KPA)
    .map((unit) => ({ ...unit, description: null, files: [], findings: 0 })),
  adoptable: 8,
};

const UNKNOWN: Finding = {
  file: CONTROLLER,
  check: "unknown-unit",
  severity: "error",
  message: "'RPM' is not a unit this project declares - did you mean 'rpm'?",
  pointer: "component.interface[3].definition.unit",
  notes: [],
};

/** RPM's panel: where it is stated, and its finding, filed at each place. */
export const UNKNOWN_RPM_PANEL: UnitReply = {
  revision: 7,
  unit: "RPM",
  description: null,
  entries: [],
  sites: [
    {
      path: CONTROLLER,
      pointer: "component.interface[3].definition.unit",
      kind: "variable",
      name: "EngineSpeed",
      component: "Controller",
      role: "reads",
    },
    {
      path: TYPES,
      pointer: "types[0].unit",
      kind: "type",
      name: "Speed_t",
      component: null,
      role: null,
    },
  ],
  findings: [UNKNOWN, { ...UNKNOWN, file: TYPES, pointer: "types[0].unit" }],
};

/** rpm's panel: its vocabulary entry, and the two variables stating it. */
export const LISTED_RPM_PANEL: UnitReply = {
  revision: 7,
  unit: "rpm",
  description: "rotational speed, revolutions per minute",
  entries: [{ file: UNITS_FILE, pointer: "units[2]" }],
  sites: [
    {
      path: SENSOR_HUB,
      pointer: "component.interface[4].definition.unit",
      kind: "variable",
      name: "EngineSpeed",
      component: "SensorHub",
      role: "produces",
    },
    {
      path: PUMP,
      pointer: "component.interface[0].definition.unit",
      kind: "variable",
      name: "PumpSpeed",
      component: "Pump",
      role: "local",
    },
  ],
  findings: [],
};

/** kPa's panel: its vocabulary entry, and nothing stating it. */
export const UNUSED_KPA_PANEL: UnitReply = {
  revision: 7,
  unit: "kPa",
  description: "pressure",
  entries: [{ file: UNITS_FILE, pointer: "units[6]" }],
  sites: [],
  findings: [],
};

/** RPM renamed onto rpm, which the vocabulary lists: the two spellings merge (merge.png). */
export const MERGE: PlanReply = {
  revision: 7,
  changes: [
    {
      file: CONTROLLER,
      fingerprint: "5e443ce41f14ce2c5cf6062cad6f583092f065e4901791ae8b63f8667f4bf78d",
      operations: [{ op: "set", pointer: "component.interface[3].definition.unit", raw: '"rpm"' }],
      hunks: [
        { line: 14, before: ['          "unit": "RPM",'], after: ['          "unit": "rpm",'] },
      ],
    },
    {
      file: TYPES,
      fingerprint: "cee6509cdb23a7a9d4daa23fa12f36312dc95ce558a20d8c74c93129bf8ac904",
      operations: [{ op: "set", pointer: "types[0].unit", raw: '"rpm"' }],
      hunks: [{ line: 6, before: ['      "unit": "RPM",'], after: ['      "unit": "rpm",'] }],
    },
  ],
};

/** rpm described anew: its entry in units.ddd.json. */
export const DESCRIPTION: PlanReply = {
  revision: 7,
  changes: [
    {
      file: UNITS_FILE,
      fingerprint: "f4dfde5af01af4f851acf7769078368fe5c90e74482b08df28b52451d7529d04",
      operations: [{ op: "set", pointer: "units[2].description", raw: '"revolutions per minute"' }],
      hunks: [
        {
          line: 6,
          before: [
            '    { "unit": "rpm", "description": "rotational speed, revolutions per minute" },',
          ],
          after: ['    { "unit": "rpm", "description": "revolutions per minute" },'],
        },
      ],
    },
  ],
};

/** RPM added to units.ddd.json, in the form its entries take. */
export const ADDITION: PlanReply = {
  revision: 7,
  changes: [
    {
      file: UNITS_FILE,
      fingerprint: "f4dfde5af01af4f851acf7769078368fe5c90e74482b08df28b52451d7529d04",
      operations: [
        { op: "insert", pointer: "units[7]", raw: '{"unit": "RPM", "description": ""}' },
      ],
      hunks: [
        {
          line: 10,
          before: ['    { "unit": "kPa", "description": "pressure" }'],
          after: [
            '    { "unit": "kPa", "description": "pressure" },',
            '    {"unit": "RPM", "description": ""}',
          ],
        },
      ],
    },
  ],
};

/** kPa taken out of units.ddd.json, with the comma before it. */
export const REMOVAL: PlanReply = {
  revision: 7,
  changes: [
    {
      file: UNITS_FILE,
      fingerprint: "f4dfde5af01af4f851acf7769078368fe5c90e74482b08df28b52451d7529d04",
      operations: [{ op: "remove", pointer: "units[6]", raw: null }],
      hunks: [
        {
          line: 9,
          before: [
            '    { "unit": "ms", "description": "time" },',
            '    { "unit": "kPa", "description": "pressure" }',
          ],
          after: ['    { "unit": "ms", "description": "time" }'],
        },
      ],
    },
  ],
};

/** The units file adoption writes for the project's eight units, line by line. */
const ADOPTED = [
  "{",
  '  "units": [',
  '    {"unit": "%", "description": ""},',
  '    {"unit": "Hz", "description": ""},',
  '    {"unit": "RPM", "description": ""},',
  '    {"unit": "V", "description": ""},',
  '    {"unit": "degC", "description": ""},',
  '    {"unit": "ms", "description": ""},',
  '    {"unit": "rpm", "description": ""},',
  '    {"unit": "°C", "description": ""}',
  "  ]",
  "}",
];

/** Adoption: the project description includes units.ddd.json, which is new (adopt.png). */
export const ADOPTION: PlanReply = {
  revision: 7,
  changes: [
    {
      file: DEMO,
      fingerprint: "c333b9667097f729ecfdadeb89b200663a6783290e4e2e65004cd74b4570a5c0",
      operations: [{ op: "insert", pointer: "project.includes[2]", raw: '"units.ddd.json"' }],
      hunks: [
        {
          line: 7,
          before: ['      "subsystems/logging/logging.ddd.json"'],
          after: ['      "subsystems/logging/logging.ddd.json",', '      "units.ddd.json"'],
        },
      ],
    },
    {
      file: UNITS_FILE,
      fingerprint: null,
      operations: [{ op: "set", pointer: "", raw: ADOPTED.join("\n") }],
      hunks: [{ line: 1, before: [], after: ADOPTED }],
    },
  ],
};
