import type {
  Finding,
  FixReply,
  PlanReply,
  ProjectUnit,
  SettleReply,
  State,
  UnitReply,
  UnitsReply,
  VariableKeyCarried,
  VariableKeyValue,
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
  message: "Controller states rpm and ×1, SensorHub states % and ×0.5",
  pointer: "component.interface[0].definition.unit",
  notes: [],
  route: { kind: "variable", name: "ValueA" },
};

/** One declaration's part of a key's answer: it may carry the key, as every declaration below
 * does for the keys it lists - `keyRows` reads `offer.carried` positionally against
 * `declarations`. */
function carried(required: boolean): VariableKeyCarried {
  return { allowed: true, required };
}

/** A kind that cannot carry the key at all, for the cell that reads "not on a parameter". */
const NOT_CARRIED: VariableKeyCarried = { allowed: false, required: false };

/** One value a key has among its declarations, as the server's `_in_play` orders them: the
 * producer's first. */
function inPlay(raw: string, components: string[], producer: boolean): VariableKeyValue {
  return { raw, components, producer };
}

/** The eleven datatypes DDD can allocate storage for (`ddd.models.common.Datatype`), in the
 * order the enum declares them - what a `datatype` key's chooser offers. */
const DATATYPES = [
  "boolean",
  "uint8",
  "sint8",
  "uint16",
  "sint16",
  "uint32",
  "sint32",
  "uint64",
  "sint64",
  "float32",
  "float64",
];

/** ValueA as the mockups show it: SensorHub produces %, Controller reads rpm, one finding;
 * Controller's conversion (×1) disagrees with the other two's (×0.5) as well, so a preview
 * carrying the producer's conversion onto it (PREVIEW_CONVERSION) is a real settlement, not a
 * no-op. Besides those two, a datatype, limits and volatile every declaration agrees about. */
export const DISAGREEING: VariableReply = {
  revision: 7,
  name: "ValueA",
  declarations: [
    {
      path: SENSOR_HUB,
      pointer: "component.interface[2].definition",
      component: "SensorHub",
      role: "produces",
      stated: {
        kind: '"measurement"',
        datatype: '"uint8"',
        unit: '"%"',
        conversion: '{"factor": 0.5}',
        limits: '{"min": 0, "max": 100}',
        volatile: "true",
      },
      type: null,
      fixed: {},
    },
    {
      path: CONTROLLER,
      pointer: "component.interface[0].definition",
      component: "Controller",
      role: "reads",
      stated: {
        kind: '"measurement"',
        datatype: '"uint8"',
        unit: '"rpm"',
        conversion: '{"factor": 1}',
        limits: '{"min": 0, "max": 100}',
        volatile: "true",
      },
      type: null,
      fixed: {},
    },
    {
      path: USER_INTERFACE,
      pointer: "component.interface[0].definition",
      component: "UserInterface",
      role: "reads",
      stated: {
        kind: '"measurement"',
        datatype: '"uint8"',
        unit: '"%"',
        conversion: '{"factor": 0.5}',
        limits: '{"min": 0, "max": 100}',
        volatile: "true",
      },
      type: null,
      fixed: {},
    },
  ],
  keys: [
    {
      key: "datatype",
      carried: [carried(true), carried(true), carried(true)],
      values: [inPlay('"uint8"', ["SensorHub", "Controller", "UserInterface"], true)],
      disagrees: false,
      editor: "datatype",
      choices: DATATYPES,
    },
    {
      key: "unit",
      carried: [carried(false), carried(false), carried(false)],
      values: [
        inPlay('"%"', ["SensorHub", "UserInterface"], true),
        inPlay('"rpm"', ["Controller"], false),
      ],
      disagrees: true,
      editor: "unit",
      choices: [],
    },
    {
      key: "conversion",
      carried: [carried(true), carried(true), carried(true)],
      values: [
        inPlay('{"factor": 0.5}', ["SensorHub", "UserInterface"], true),
        inPlay('{"factor": 1}', ["Controller"], false),
      ],
      disagrees: true,
      editor: "none",
      choices: [],
    },
    {
      key: "limits",
      carried: [carried(false), carried(false), carried(false)],
      values: [
        inPlay('{"min": 0, "max": 100}', ["SensorHub", "Controller", "UserInterface"], true),
      ],
      disagrees: false,
      editor: "limits",
      choices: [],
    },
    {
      key: "volatile",
      carried: [carried(true), carried(true), carried(true)],
      values: [inPlay("true", ["SensorHub", "Controller", "UserInterface"], true)],
      disagrees: false,
      editor: "volatile",
      choices: [],
    },
  ],
  findings: [MISMATCH],
};

/** The same declarations settled: Controller reads % and ×0.5 too, and both disagreements are
 * gone. */
export const AGREEING: VariableReply = {
  ...DISAGREEING,
  declarations: DISAGREEING.declarations.map((declaration) =>
    declaration.component === "Controller"
      ? {
          ...declaration,
          stated: { ...declaration.stated, unit: '"%"', conversion: '{"factor": 0.5}' },
        }
      : declaration,
  ),
  keys: DISAGREEING.keys.map((offer) => {
    if (offer.key === "unit") {
      return {
        ...offer,
        values: [inPlay('"%"', ["SensorHub", "Controller", "UserInterface"], true)],
        disagrees: false,
      };
    }
    if (offer.key === "conversion") {
      return {
        ...offer,
        values: [inPlay('{"factor": 0.5}', ["SensorHub", "Controller", "UserInterface"], true)],
        disagrees: false,
      };
    }
    return offer;
  }),
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
  keys: [
    {
      key: "unit",
      carried: [carried(false)],
      values: [inPlay('"rpm"', ["SensorHub"], true)],
      disagrees: false,
      editor: "unit",
      choices: [],
    },
  ],
  findings: [],
};

/** An axis two components declare: SensorHub's 8 points index EngineSpeed, and Controller's
 * limits disagree with it - for a naming chooser (`input`) and a range (`limits`). */
export const SHAPED: VariableReply = {
  revision: 7,
  name: "Rpm_Axis",
  declarations: [
    {
      path: SENSOR_HUB,
      pointer: "component.interface[3].definition",
      component: "SensorHub",
      role: "produces",
      stated: {
        kind: '"axis"',
        datatype: '"uint16"',
        unit: '"rpm"',
        size: "8",
        input: '"EngineSpeed"',
        limits: '{"min": 0, "max": 8000}',
      },
      type: null,
      fixed: {},
    },
    {
      path: CONTROLLER,
      pointer: "component.interface[1].definition",
      component: "Controller",
      role: "reads",
      stated: {
        kind: '"axis"',
        datatype: '"uint16"',
        unit: '"rpm"',
        size: "8",
        input: '"EngineSpeed"',
        limits: '{"min": 0, "max": 6000}',
      },
      type: null,
      fixed: {},
    },
  ],
  keys: [
    {
      key: "size",
      carried: [carried(true), carried(true)],
      values: [inPlay("8", ["SensorHub", "Controller"], true)],
      disagrees: false,
      editor: "size",
      choices: ["ADC_SAMPLES", "PRESSURE_CELLS"],
    },
    {
      key: "limits",
      carried: [carried(false), carried(false)],
      values: [
        inPlay('{"min": 0, "max": 8000}', ["SensorHub"], true),
        inPlay('{"min": 0, "max": 6000}', ["Controller"], false),
      ],
      disagrees: true,
      editor: "limits",
      choices: [],
    },
    {
      key: "input",
      carried: [carried(false), carried(false)],
      values: [inPlay('"EngineSpeed"', ["SensorHub", "Controller"], true)],
      disagrees: false,
      editor: "name",
      choices: ["EngineSpeed", "OilPressure"],
    },
  ],
  findings: [],
};

/** SharedName as a measurement SensorHub produces, with dimensions, and as a parameter Pump
 * declares too: the "not on a parameter" cell. */
export const MIXED_KINDS: VariableReply = {
  revision: 7,
  name: "SharedName",
  declarations: [
    {
      path: SENSOR_HUB,
      pointer: "component.interface[5].definition",
      component: "SensorHub",
      role: "produces",
      stated: { kind: '"measurement"', datatype: '"uint8"', unit: '"%"', dimensions: "[4]" },
      type: null,
      fixed: {},
    },
    {
      path: PUMP,
      pointer: "component.interface[1].definition",
      component: "Pump",
      role: "local",
      stated: { kind: '"parameter"', datatype: '"uint8"', unit: '"%"' },
      type: null,
      fixed: {},
    },
  ],
  keys: [
    {
      key: "datatype",
      carried: [carried(true), carried(true)],
      values: [inPlay('"uint8"', ["SensorHub", "Pump"], true)],
      disagrees: false,
      editor: "datatype",
      choices: DATATYPES,
    },
    {
      key: "unit",
      carried: [carried(false), carried(false)],
      values: [inPlay('"%"', ["SensorHub", "Pump"], true)],
      disagrees: false,
      editor: "unit",
      choices: [],
    },
    {
      key: "dimensions",
      carried: [carried(false), NOT_CARRIED],
      values: [inPlay("[4]", ["SensorHub"], true)],
      disagrees: false,
      editor: "none",
      choices: [],
    },
  ],
  findings: [],
};

/** A preview that settles ValueA's conversion onto Controller too, beside DISAGREEING's own
 * unit mismatch: the table's "will change" tag, and Show changes, have something to draw. */
export const PREVIEW_CONVERSION: SettleReply = {
  revision: 7,
  changes: [
    {
      file: CONTROLLER,
      fingerprint: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      operations: [
        {
          op: "set",
          pointer: "component.interface[0].definition.conversion",
          raw: '{"factor": 0.5}',
        },
      ],
      hunks: [
        {
          line: 14,
          before: ['          "conversion": {"factor": 1},'],
          after: ['          "conversion": {"factor": 0.5},'],
        },
      ],
    },
  ],
};

/** A preview that settles Rpm_Axis's limits onto Controller too, resolving SHAPED's own
 * disagreement: the table's "will change" tag, and Show changes, have something to draw. */
export const PREVIEW_LIMITS: SettleReply = {
  revision: 7,
  changes: [
    {
      file: CONTROLLER,
      fingerprint: "3c9909afec25354d551dae21590bb26e38d53f2173b8d3dc3eee4c047e7ab1c1",
      operations: [
        {
          op: "set",
          pointer: "component.interface[1].definition.limits",
          raw: '{"min": 0, "max": 8000}',
        },
      ],
      hunks: [
        {
          line: 18,
          before: ['          "limits": {"min": 0, "max": 6000},'],
          after: ['          "limits": {"min": 0, "max": 8000},'],
        },
      ],
    },
  ],
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
  route: { kind: "unit", name: "RPM" },
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

// The Findings tab (spec 5.1, 5.2): one finding of each severity, one leading to a variable, one
// to a unit, one to a component, and one leading nowhere because its file did not load.

/** SensorHub's ValueA, the one declaration with no id: leads to its variable's panel, and is the
 * finding `ID_FIX` carries a fix for. */
export const MISSING_ID: Finding = {
  file: SENSOR_HUB,
  check: "missing-id",
  severity: "error",
  message:
    "'ValueA' has no 'id', so a later delivery that renames it reports a removal and an " +
    "unrelated addition; 'ddd id --assign' writes one",
  pointer: "component.interface[2].definition.name",
  notes: [],
  route: { kind: "variable", name: "ValueA" },
};

/** RPM, stated by Controller's EngineSpeed and mirrored onto the type that also states it: leads
 * to its unit's panel, with a note for the other site. */
export const UNKNOWN_RPM_FINDING: Finding = {
  file: CONTROLLER,
  check: "unknown-unit",
  severity: "warning",
  message: "'RPM' is not a unit this project declares - did you mean 'rpm'?",
  pointer: "component.interface[3].definition.unit",
  notes: [{ message: "Also stated by 'Speed_t'", file: TYPES, pointer: "types[0].unit" }],
  route: { kind: "unit", name: "RPM" },
};

/** UserInterface sharing its name with another component: not within a declaration, so it leads
 * to the component's own page rather than a variable's panel. */
const DUPLICATE_COMPONENT: Finding = {
  file: USER_INTERFACE,
  check: "duplicate-component",
  severity: "info",
  message: "Another component in this project is also named 'UserInterface'",
  pointer: "component.name",
  notes: [],
  route: { kind: "component", name: null },
};

/** Pump's ValueB, filed on a file that did not load: the row says so instead of leading nowhere
 * silently. */
export const STORAGE_MISMATCH: Finding = {
  file: PUMP,
  check: "storage-mismatch",
  severity: "error",
  message: "'ValueB' is stored as uint16 here but uint8 elsewhere",
  pointer: "component.interface[1].definition",
  notes: [
    {
      message: "Stored as uint8",
      file: SENSOR_HUB,
      pointer: "component.interface[1].definition.datatype",
    },
  ],
  route: null,
};

/** The project of spec 6's screenshots: every severity, every route a finding can lead to, and
 * one whose file did not load - pump.ddd.json, still listed as the analysis last read it. */
export const PROJECT_FINDINGS: State = {
  revision: 7,
  project: DEMO,
  files: [
    {
      path: CONTROLLER,
      kind: "component",
      name: "Controller",
      loaded: true,
      fingerprint: "a",
      findings: { error: 0, warning: 1, info: 0 },
    },
    {
      path: PUMP,
      kind: "component",
      name: null,
      loaded: false,
      fingerprint: "b",
      findings: { error: 1, warning: 0, info: 0 },
    },
    {
      path: SENSOR_HUB,
      kind: "component",
      name: "SensorHub",
      loaded: true,
      fingerprint: "c",
      findings: { error: 1, warning: 0, info: 0 },
    },
    {
      path: USER_INTERFACE,
      kind: "component",
      name: "UserInterface",
      loaded: true,
      fingerprint: "d",
      findings: { error: 0, warning: 0, info: 1 },
    },
  ],
  findings: [MISSING_ID, STORAGE_MISMATCH, UNKNOWN_RPM_FINDING, DUPLICATE_COMPONENT],
};

/** The one fix the tab offers: `missing-id`, previewed onto SensorHub's ValueA. */
export const ID_FIX: FixReply = {
  revision: 7,
  fixes: [
    {
      title: "Give 'ValueA' an id",
      changes: [
        {
          file: SENSOR_HUB,
          fingerprint: "c",
          operations: [
            { op: "set", pointer: "component.interface[2].definition.id", raw: '"rbdtf7g2eey1"' },
          ],
          hunks: [
            {
              line: 13,
              before: ['          "name": "ValueA",'],
              after: ['          "name": "ValueA",', '          "id": "rbdtf7g2eey1",'],
            },
          ],
        },
      ],
    },
  ],
};

/** A project with nothing to report. */
export const NO_FINDINGS: State = {
  revision: 7,
  project: DEMO,
  files: [
    {
      path: CONTROLLER,
      kind: "component",
      name: "Controller",
      loaded: true,
      fingerprint: "a",
      findings: { error: 0, warning: 0, info: 0 },
    },
    {
      path: SENSOR_HUB,
      kind: "component",
      name: "SensorHub",
      loaded: true,
      fingerprint: "c",
      findings: { error: 0, warning: 0, info: 0 },
    },
  ],
  findings: [],
};
