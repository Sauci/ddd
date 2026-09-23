import type {
  DeclarableName,
  DeclarableReply,
  Finding,
  FixReply,
  GridAxis,
  KindForm,
  PlanReply,
  ProjectUnit,
  SettleReply,
  State,
  TypeReply,
  TypesReply,
  UndoPreview,
  UnitReply,
  UnitsReply,
  ValuesReply,
  VariableKeyCarried,
  VariableKeyOffer,
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
 * finding `ID_FIX` carries a fix for. `missing-id`'s own default is info
 * (`src/ddd/diagnostics.py`). */
export const MISSING_ID: Finding = {
  file: SENSOR_HUB,
  check: "missing-id",
  severity: "info",
  message:
    "'ValueA' has no 'id', so a later delivery that renames it reports a removal and an " +
    "unrelated addition; 'ddd id --assign' writes one",
  pointer: "component.interface[2].definition.name",
  notes: [],
  route: { kind: "variable", name: "ValueA" },
};

/** RPM, where Controller's EngineSpeed states it: leads to its unit's panel, which is where
 * every other place stating it is listed - the check files one finding per place rather than
 * noting the others here (`_check_units` in `src/ddd/analysis.py`). `unknown-unit`'s own default
 * is error, and it is the one check whose route is ever a unit's (`src/ddd/finding_routes.py`'s
 * `UNIT_CHECKS`). */
export const UNKNOWN_RPM_FINDING: Finding = {
  file: CONTROLLER,
  check: "unknown-unit",
  severity: "error",
  message: "'RPM' is not a unit this project declares - did you mean 'rpm'?",
  pointer: "component.interface[3].definition.unit",
  notes: [],
  route: { kind: "unit", name: "RPM" },
};

/** UserInterface measuring in a raster no file of the project declares: filed on the component
 * itself rather than inside a declaration, so it leads to the component's own page rather than
 * to a variable's panel. `unknown-raster`'s own default is error. */
const UNKNOWN_RASTER: Finding = {
  file: USER_INTERFACE,
  check: "unknown-raster",
  severity: "error",
  message:
    "component 'UserInterface' measures in '20ms', which is not a raster any file of this " +
    "project declares - did you mean '10ms'?",
  pointer: "component.raster",
  notes: [],
  route: { kind: "component", name: null },
};

/** Controller and SensorHub presenting ValueB differently in the a2l: the producer's value wins,
 * and the finding is filed on the declaration that disagrees with it, with a note naming the one
 * it was compared against. `storage-mismatch`'s own default is warning, and it compares the a2l
 * keys alone (`_STORAGE_FIELDS` in `src/ddd/analysis.py`). */
export const STORAGE_MISMATCH: Finding = {
  file: CONTROLLER,
  check: "storage-mismatch",
  severity: "warning",
  message:
    "'ValueB': component 'Controller' specifies a different a2l format than 'SensorHub' " +
    "(a2l format: '%6.2' != '%6.3'); the value of 'SensorHub' is used",
  pointer: "component.interface[1].definition",
  notes: [
    {
      message: "reference declaration",
      file: SENSOR_HUB,
      pointer: "component.interface[1].definition",
    },
  ],
  route: { kind: "variable", name: "ValueB" },
};

/** Pump's file, which has no component name at all: a `schema` error is one of the four checks
 * that mean a file did not load (`ddd.lsp.navigation.LOAD_CHECKS`), so the analysis read no
 * document for the pointer to describe and the finding leads nowhere - the row says so instead
 * of leading nowhere silently. The file's own entry says as much: `loaded: false`, and no name,
 * since the key that names it is the one it is missing. */
export const DID_NOT_LOAD: Finding = {
  file: PUMP,
  check: "schema",
  severity: "error",
  message: "Field required",
  pointer: "component.name",
  notes: [],
  route: null,
};

/** The project of spec 6's screenshots: every severity, every route a finding can lead to, and
 * one whose file did not load - pump.ddd.json, still listed as the analysis last read it. In the
 * order `GET /api/state` answers, which is by file: controller's `unknown-unit` (error) and
 * `storage-mismatch` (warning), pump's `schema` (error), sensor_hub's `missing-id` (info), and
 * user_interface's `unknown-raster` (error) - each check's own default severity,
 * `src/ddd/diagnostics.py`. The tab sorts them worst first. */
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
      findings: { error: 1, warning: 1, info: 0 },
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
      findings: { error: 0, warning: 0, info: 1 },
    },
    {
      path: USER_INTERFACE,
      kind: "component",
      name: "UserInterface",
      loaded: true,
      fingerprint: "d",
      findings: { error: 1, warning: 0, info: 0 },
    },
  ],
  findings: [UNKNOWN_RPM_FINDING, STORAGE_MISMATCH, DID_NOT_LOAD, MISSING_ID, UNKNOWN_RASTER],
  undoable: null,
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
  undoable: null,
};

/** What `GET /api/undo` answers for an adoption: the project description put back a line, and
 * the units file that edit created taken away again - the two shapes a change of an undo has. */
export const UNDO_ADOPTION: UndoPreview = {
  revision: 7,
  at: 3,
  label: "the vocabulary adopted",
  changes: [
    {
      file: DEMO,
      gone: false,
      hunks: [
        {
          line: 6,
          before: ['      "components/pump.ddd.json",', '      "units.ddd.json"'],
          after: ['      "components/pump.ddd.json"'],
        },
      ],
    },
    {
      file: "C:/work/demo/units.ddd.json",
      gone: true,
      hunks: [
        {
          line: 1,
          before: ["{", '  "units": [', '    { "unit": "rpm", "description": "" }', "  ]", "}"],
          after: [],
        },
      ],
    },
  ],
};

/** Types modelled on examples/structures, as GET /api/types answers them - not transcribed from
 * it: SensorCal_t's `uses: 0` here (the real example names it once) gives the table's zero-count
 * blank-cell case a row to draw. */
export const PROJECT_TYPES: TypesReply = {
  revision: 7,
  types: [
    {
      name: "DriverStatus_t",
      kind: "external",
      description: "The raw state of the vendor's sensor driver",
      uses: 1,
      findings: 0,
    },
    {
      name: "Sample_t",
      kind: "struct",
      description: "One reading and the instant it was taken",
      uses: 1,
      findings: 0,
    },
    {
      name: "SensorCal_t",
      kind: "struct",
      description: "What one sensor exposes to the calibration tool",
      uses: 0,
      findings: 0,
    },
    {
      name: "Sensor_t",
      kind: "struct",
      description: "Everything one sensor measures",
      uses: 2,
      findings: 0,
    },
    {
      name: "Status_t",
      kind: "struct",
      description: "Flags packed into one word, as c bitfields",
      uses: 1,
      findings: 1,
    },
    {
      name: "Temperature_t",
      kind: "scalar",
      description: "A temperature as every component of this project agrees to see it",
      uses: 3,
      findings: 0,
    },
  ],
};

/** A project that declares none, for the story that says so. */
export const NO_TYPES: TypesReply = { revision: 7, types: [] };

// One type's own panel (spec 5.2), modelled on examples/structures/types.ddd.json - not
// transcribed from it, as PROJECT_TYPES already is not: the same six types, the same names and
// descriptions, Sensor_t's two components renamed to this file's own Windows-style paths.

/** Sensor_t is declared by two components: Sensing produces Inlet, Monitoring reads it - the
 * "Where it is used" table's two rows sharing one name, told apart by component and role. */
const SENSING = "C:/work/demo/components/sensing.ddd.json";
const MONITORING = "C:/work/demo/components/monitoring.ddd.json";

/** Temperature_t: its four keys, each an `offer_for` offer - one carried, at most one value,
 * `components: []` and `producer: false` since a type states a key itself, nothing "carries" it
 * the way a declaration does. Used three times, each a structure member, never as a variable. */
export const SCALAR_TYPE: TypeReply = {
  revision: 7,
  name: "Temperature_t",
  kind: "scalar",
  file: TYPES,
  pointer: "types[0]",
  description: "A temperature as every component of this project agrees to see it",
  header: null,
  keys: [
    {
      key: "datatype",
      carried: [carried(true)],
      values: [inPlay('"uint16"', [], false)],
      disagrees: false,
      editor: "datatype",
      choices: DATATYPES,
    },
    {
      key: "unit",
      carried: [carried(false)],
      values: [inPlay('"degC"', [], false)],
      disagrees: false,
      editor: "unit",
      choices: [],
    },
    {
      key: "conversion",
      carried: [carried(true)],
      values: [inPlay('{"factor": 0.1, "offset": -40}', [], false)],
      disagrees: false,
      editor: "none",
      choices: [],
    },
    {
      key: "limits",
      carried: [carried(false)],
      values: [inPlay('{"min": -40, "max": 150}', [], false)],
      disagrees: false,
      editor: "limits",
      choices: [],
    },
  ],
  uses: [
    {
      path: TYPES,
      pointer: "types[2].members[0].typename",
      kind: "member",
      name: "Sample_t.value",
      component: null,
      role: null,
    },
    {
      path: TYPES,
      pointer: "types[4].members[3].typename",
      kind: "member",
      name: "Sensor_t.history",
      component: null,
      role: null,
    },
    {
      path: TYPES,
      pointer: "types[5].members[0].typename",
      kind: "member",
      name: "SensorCal_t.warnLimit",
      component: null,
      role: null,
    },
  ],
  members: [],
  findings: [],
};

/** Sensor_t filed as the second of two types sharing its name - Sensing's own inline types list,
 * left over from before types.ddd.json existed, still declares one too. The panel's Findings
 * section (part 4) needs a type carrying a real finding to be drawn at all; the table's own
 * fixture already counts one against Status_t (`PROJECT_TYPES`), so a structure carrying one
 * here is the same story told in full. */
const DUPLICATE_SENSOR: Finding = {
  file: TYPES,
  check: "duplicate-type",
  severity: "error",
  message: "type 'Sensor_t' is already declared",
  pointer: "types[4]",
  notes: [{ message: "first declared here", file: SENSING, pointer: "component.types[0]" }],
  route: { kind: "type", name: "Sensor_t" },
};

/** Sensor_t: no keys - a structure fixes nothing a chooser edits - four members, the last with
 * dimensions, the two declarations naming it, produced by Sensing and read by Monitoring, and
 * one finding. */
export const STRUCT_TYPE: TypeReply = {
  revision: 7,
  name: "Sensor_t",
  kind: "struct",
  file: TYPES,
  pointer: "types[4]",
  description: "Everything one sensor measures",
  header: null,
  keys: [],
  uses: [
    {
      path: SENSING,
      pointer: "component.interface[1].definition.typename",
      kind: "variable",
      name: "Inlet",
      component: "Sensing",
      role: "produces",
    },
    {
      path: MONITORING,
      pointer: "component.interface[0].definition.typename",
      kind: "variable",
      name: "Inlet",
      component: "Monitoring",
      role: "reads",
    },
  ],
  members: [
    {
      name: "latest",
      member: "value",
      typename: "Sample_t",
      datatype: null,
      unit: null,
      bits: null,
      dimensions: [],
    },
    {
      name: "status",
      member: "value",
      typename: "Status_t",
      datatype: null,
      unit: null,
      bits: null,
      dimensions: [],
    },
    {
      name: "driver",
      member: "value",
      typename: "DriverStatus_t",
      datatype: null,
      unit: null,
      bits: null,
      dimensions: [],
    },
    {
      name: "history",
      member: "value",
      typename: "Temperature_t",
      datatype: null,
      unit: null,
      bits: null,
      dimensions: ["8"],
    },
  ],
  findings: [DUPLICATE_SENSOR],
};

/** DriverStatus_t: an external type's own header, and its one use - Sensor_t's driver member. */
export const EXTERNAL_TYPE: TypeReply = {
  revision: 7,
  name: "DriverStatus_t",
  kind: "external",
  file: TYPES,
  pointer: "types[1]",
  description: "The raw state of the vendor's sensor driver",
  header: "driver_status.h",
  keys: [],
  uses: [
    {
      path: TYPES,
      pointer: "types[4].members[2].typename",
      kind: "member",
      name: "Sensor_t.driver",
      component: null,
      role: null,
    },
  ],
  members: [],
  findings: [],
};

/** Temperature_t's unit changed to K: the panel's own preview, for the key-chosen stories. */
export const SET_UNIT: PlanReply = {
  revision: 7,
  changes: [
    {
      file: TYPES,
      fingerprint: "d4a3f1c6b2e5978a0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b",
      operations: [{ op: "set", pointer: "types[0].unit", raw: '"K"' }],
      hunks: [{ line: 9, before: ['      "unit": "degC",'], after: ['      "unit": "K",'] }],
    },
  ],
};

// Part 7's declare panel (spec 5.2): the real `GET /api/declarable` answer for examples/demo's
// Controller, transcribed from .superpowers/sdd/2026-09-23-gui-declarations/declarable-
// controller.json rather than written by hand.

/** One key a new declaration may state, as the endpoint offers it: nothing is in play yet, so
 * every key's `values` is empty and nothing disagrees. */
function keyOffer(
  key: string,
  required: boolean,
  editor: VariableKeyOffer["editor"],
  choices: string[] = [],
): VariableKeyOffer {
  return { key, carried: [carried(required)], values: [], disagrees: false, editor, choices };
}

const TYPENAMES = ["DriverState_t", "SensorDiagnosis_t"];
const AXES = ["AxisA", "AxisB"];

/** The five keys every one of the six kinds offers alike: the storage a declaration names
 * (`datatype` or `typename`), `unit`, a composed `conversion`, and `limits` - none of them
 * required, and none of them a field `DeclarePanelView` draws (`keysOf`, `gui/src/lib/
 * declarations.ts`). */
const STORAGE_AND_UNIT_KEYS: VariableKeyOffer[] = [
  keyOffer("datatype", false, "datatype", DATATYPES),
  keyOffer("typename", false, "typename", TYPENAMES),
  keyOffer("unit", false, "unit"),
  keyOffer("conversion", false, "none"),
  keyOffer("limits", false, "limits"),
];

/** What `examples/demo`'s Controller may declare: the nine names another component already
 * produces and Controller does not yet read, and the six kinds a new name may take. */
export const DECLARABLE: DeclarableReply = {
  revision: 1,
  file: CONTROLLER,
  names: [
    { name: "BlockA", kind: "value_block", producer: "UserInterface", scopes: ["input"] },
    { name: "CurveB", kind: "curve", producer: "UserInterface", scopes: ["input"] },
    { name: "Diagnosis", kind: "measurement", producer: "SensorHub", scopes: ["input"] },
    { name: "FlagA", kind: "measurement", producer: "SensorHub", scopes: ["input"] },
    { name: "ValueC", kind: "measurement", producer: "SensorHub", scopes: ["input"] },
    { name: "ValueD", kind: "measurement", producer: "SensorHub", scopes: ["input"] },
    { name: "ValueI", kind: "measurement", producer: "UserInterface", scopes: ["input"] },
    { name: "ValueJ", kind: "measurement", producer: "EventLogger", scopes: ["input"] },
    { name: "ValueK", kind: "measurement", producer: "EventLogger", scopes: ["input"] },
  ] satisfies DeclarableName[],
  kinds: [
    {
      kind: "measurement",
      keys: [
        ...STORAGE_AND_UNIT_KEYS,
        keyOffer("dimensions", false, "none"),
        keyOffer("volatile", true, "volatile"),
      ],
    },
    {
      kind: "parameter",
      keys: [...STORAGE_AND_UNIT_KEYS, keyOffer("volatile", true, "volatile")],
    },
    {
      kind: "value_block",
      keys: [
        ...STORAGE_AND_UNIT_KEYS,
        keyOffer("dimensions", true, "none"),
        keyOffer("volatile", true, "volatile"),
      ],
    },
    {
      kind: "curve",
      keys: [
        ...STORAGE_AND_UNIT_KEYS,
        keyOffer("volatile", true, "volatile"),
        keyOffer("axis", true, "name", AXES),
      ],
    },
    {
      kind: "map",
      keys: [
        ...STORAGE_AND_UNIT_KEYS,
        keyOffer("volatile", true, "volatile"),
        keyOffer("x_axis", true, "name", AXES),
        keyOffer("y_axis", true, "name", AXES),
      ],
    },
    {
      kind: "axis",
      keys: [
        ...STORAGE_AND_UNIT_KEYS,
        keyOffer("size", true, "size"),
        keyOffer("volatile", true, "volatile"),
        keyOffer("input", false, "name", [
          "Diagnosis",
          "FlagA",
          "StateA",
          "StateName",
          "ValueA",
          "ValueB",
          "ValueC",
          "ValueD",
          "ValueE",
          "ValueF",
          "ValueG",
          "ValueH",
          "ValueI",
          "ValueJ",
          "ValueK",
        ]),
      ],
    },
  ] satisfies KindForm[],
  scopes: ["output", "input", "local"],
  // Measured: `examples/demo` declares no constants, so a dimension of BlockC is a number
  // typed and nothing else. `DimensionsField`'s own stories carry the other case.
  constants: [],
};

// ValuesGridView (docs/superpowers/plans/2026-09-23-gui-values.md, task 5): GET /api/values
// answers, measured off the running server against examples/demo rather than read off its files
// directly - a file's own conversion is not what it reads back as once resolved (see task-5-
// brief.md's own prerequisites table, and objectValues.test.ts's own CurveA/MapA/BlockA answers,
// which these mirror field for field under this file's own C:/work/demo paths).

/** AxisA: Hz, ×0.25, the six points CurveA, CurveB and MapA's x_axis all read through - and, for
 * `position: "axis"`, MapA's y_axis is never this: an axis's own reference is never an axis. */
function axisA(position: string): GridAxis {
  return {
    position,
    name: "AxisA",
    unit: "Hz",
    breakpoints: [0, 3200, 6400, 12800, 19200, 32000],
    conversion: { kind: "linear", factor: 0.25, offset: 0 },
  };
}

/** AxisB: %, ×0.5, MapA's own y_axis alone. */
function axisB(position: string): GridAxis {
  return {
    position,
    name: "AxisB",
    unit: "%",
    breakpoints: [0, 60, 140, 200],
    conversion: { kind: "linear", factor: 0.5, offset: 0 },
  };
}

/** CurveA: one row against AxisA, both linear - ACurveAgainstItsAxis and ACurveInRawCounts'
 * shared fixture, the raw/physical toggle being the only thing that differs between them. Index
 * 2 (currently 800) is ACellMidChange's own edit, to 750. */
export const VALUES_CURVE: ValuesReply = {
  revision: 1,
  name: "CurveA",
  kind: "curve",
  datatype: "uint16",
  unit: "ms",
  conversion: { kind: "linear", factor: 0.01, offset: 0 },
  minimum: 0,
  maximum: 655.35,
  shape: [6],
  rows: [[1200, 900, 800, 750, 700, 650]],
  stated: "array",
  axes: [axisA("axis")],
  owner: "Controller",
  file: CONTROLLER,
  findings: [],
};

/** MapA: four rows of six, x_axis AxisA and y_axis AxisB - AMapWithBothHeaders exists to prove
 * its row labels are AxisB's own readings (0, 30, 70, 100 physical) and not indices. */
export const VALUES_MAP: ValuesReply = {
  revision: 1,
  name: "MapA",
  kind: "map",
  datatype: "sint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: -64,
  maximum: 63.5,
  shape: [4, 6],
  rows: [
    [20, 24, 28, 30, 32, 30],
    [18, 22, 26, 28, 30, 28],
    [12, 16, 20, 22, 24, 22],
    [6, 10, 14, 16, 18, 16],
  ],
  stated: "array",
  axes: [axisA("x_axis"), axisB("y_axis")],
  owner: "Controller",
  file: CONTROLLER,
  findings: [],
};

/** BlockA: one row of eight against no axis at all, and the identity conversion, so physical and
 * raw read the same - AValueBlockOverIndices' own column header is plain indices. */
export const VALUES_BLOCK: ValuesReply = {
  revision: 1,
  name: "BlockA",
  kind: "value_block",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "identity" },
  minimum: 0,
  maximum: 255,
  shape: [8],
  rows: [[0, 12, 28, 52, 84, 124, 180, 255]],
  stated: "array",
  axes: [],
  owner: "UserInterface",
  file: USER_INTERFACE,
  findings: [],
};

/** AxisA drawn as an object in its own right, rather than as CurveA's or MapA's own axis: it
 * carries no axis of its own, so AnAxisOnItsOwn's column header is plain indices too - what makes
 * it worth drawing beside AValueBlockOverIndices rather than redundant with it. */
export const VALUES_AXIS: ValuesReply = {
  revision: 1,
  name: "AxisA",
  kind: "axis",
  datatype: "uint16",
  unit: "Hz",
  conversion: { kind: "linear", factor: 0.25, offset: 0 },
  minimum: 0,
  maximum: 16383.75,
  shape: [6],
  rows: [[0, 3200, 6400, 12800, 19200, 32000]],
  stated: "array",
  axes: [],
  owner: "Controller",
  file: CONTROLLER,
  findings: [],
};

/** CurveB: one value, 200, standing for all six cells against AxisA - AScalarInitStatedOnce's
 * own "stated once" note. */
export const VALUES_CURVE_B: ValuesReply = {
  revision: 1,
  name: "CurveB",
  kind: "curve",
  datatype: "uint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: 0,
  maximum: 127.5,
  shape: [6],
  rows: [[200, 200, 200, 200, 200, 200]],
  stated: "scalar",
  axes: [axisA("axis")],
  owner: "UserInterface",
  file: USER_INTERFACE,
  findings: [],
};

/** ValueD: SensorHub's own real absent init - a measurement declared with `dimensions: [8]` and
 * no `init` at all (sensor_hub.ddd.json), so the startup code zeroes it - AnAbsentInitGreyed's
 * own "nothing is stated" note. No unit, the identity conversion, and no axis: a plain shaped
 * measurement, not a curve or a map. */
export const VALUES_VALUE_D: ValuesReply = {
  revision: 1,
  name: "ValueD",
  kind: "measurement",
  datatype: "uint16",
  unit: "",
  conversion: { kind: "identity" },
  minimum: 0,
  maximum: 65535,
  shape: [8],
  rows: [[0, 0, 0, 0, 0, 0, 0, 0]],
  stated: "none",
  axes: [],
  owner: "SensorHub",
  file: SENSOR_HUB,
  findings: [],
};

/** SoftwareLabel: initialised with text ("V1.2.3", `conversion: { kind: "string" }`) rather than
 * a grid at all - ATextInit's own line, with no grid under it. */
export const VALUES_SOFTWARE_LABEL: ValuesReply = {
  revision: 1,
  name: "SoftwareLabel",
  kind: "value_block",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "string" },
  minimum: 0,
  maximum: 255,
  shape: [16],
  rows: [],
  stated: "text",
  axes: [],
  owner: "Controller",
  file: CONTROLLER,
  findings: [],
};

/** CurveA's own element [2] (controller.ddd.json:205, currently 800, inline with the rest of its
 * row) set to 750 - ACellMidChange's preview, the same cell objectValues.test.ts's cellSentence
 * test pins (750 raw reads 7.5 ms). */
export const CURVE_CELL_PLAN: PlanReply = {
  revision: 1,
  changes: [
    {
      file: CONTROLLER,
      fingerprint: "b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8",
      operations: [
        { op: "set", pointer: "component.interface[12].definition.init[2]", raw: "750" },
      ],
      hunks: [
        {
          line: 205,
          before: ['          "init": [1200, 900, 800, 750, 700, 650],'],
          after: ['          "init": [1200, 900, 750, 750, 700, 650],'],
        },
      ],
    },
  ],
};
