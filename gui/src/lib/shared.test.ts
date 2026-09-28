import { describe, expect, test } from "vitest";
import type { PlanReply, SharedEntry, SharedReply } from "../api/types";
import {
  addTitle,
  constantAdd,
  isDeclared,
  kindNamed,
  planEdit,
  rasterRaw,
  rasterSet,
  rowKey,
  SECTION_ACCESSES,
  SHARED_KINDS,
  SHARED_VOCABULARIES,
  sectionAdd,
  sectionRaw,
  sectionRemoveBlocked,
  sectionSet,
  selectionAt,
  tabTitle,
  vocabularyOf,
} from "./shared";

const reply = (names: string[]): SharedReply => ({
  revision: 1,
  entries: names.map((name) => ({
    kind: "constant",
    name,
    states: "16",
    uses: 0,
    findings: 0,
  })),
});

/** A constant and a section both called FOO - a table of the one shape a row keyed by name alone
 * could not tell apart. `SECTION_NAME_PATTERN` is `[A-Za-z0-9_.$]+`, so a section called FOO is a
 * name the loader takes, and the kind is then the only thing between the two rows. */
const ONE_SPELLING: SharedReply = {
  revision: 1,
  entries: [
    { kind: "constant", name: "FOO", states: "4", uses: 0, findings: 0 },
    { kind: "section", name: "FOO", states: "read-write, align 4", uses: 0, findings: 0 },
  ],
};

/** A `SharedEntry` per kind word, named `N0`, `N1`, ... so a row is never mistaken for another of
 * the same kind - `tabTitle` counts by `kind` alone, and the name only has to keep entries apart. */
function entries(kinds: string[]): SharedEntry[] {
  return kinds.map((kind, index) => ({
    kind,
    name: `N${index}`,
    states: "x",
    uses: 0,
    findings: 0,
  }));
}

describe("the tab's summary line", () => {
  test("names each vocabulary that has entries", () => {
    expect(tabTitle(entries(["constant", "constant", "section"]))).toBe("2 constants · 1 section");
  });

  test("counts a third vocabulary exactly as the first two - it does not know their words", () => {
    // A `for (const kind of ["constant", "section"])` fixed to the two vocabularies known today
    // would pass every other test in this file without ever consulting a third word. `raster` is
    // not one the tab holds yet; `tabTitle` does not need to know that; it counts whichever kinds
    // `entries` actually carries, which is what makes the next vocabulary a data change.
    expect(tabTitle(entries(["constant", "raster", "raster", "section"]))).toBe(
      "1 constant · 2 rasters · 1 section",
    );
  });

  test("says one of a kind in the singular", () => {
    // Part 13 shipped a plural no assertion could tell from the wrong one, because "1 shape" is a
    // substring of "1 shapes". `toBe` on the whole line is what catches a mutation that always
    // pluralises.
    expect(tabTitle(entries(["constant"]))).toBe("1 constant");
  });

  test("names only the kinds that have any", () => {
    expect(tabTitle(entries(["section", "section"]))).toBe("2 sections");
  });

  test("says a project with none declares none", () => {
    expect(tabTitle([])).toBe("This project declares nothing in its shared files.");
  });
});

describe("whether a name is declared", () => {
  test("a name the table holds is declared", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "constant", "TREND_SAMPLES")).toBe(true);
  });

  test("a name it does not hold is not - which is what opens the add form", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "constant", "CELLS")).toBe(false);
  });

  test("a name of another kind is not, however it is spelled", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "section", "TREND_SAMPLES")).toBe(false);
  });
});

describe("which vocabularies the tab holds", () => {
  test("offers all three, constants first - the order the server walks and sorts them in", () => {
    expect(SHARED_VOCABULARIES).toEqual(["constant", "section", "raster"]);
  });

  test("names each by its plural, which is also its file's own word", () => {
    expect(SHARED_VOCABULARIES.map(vocabularyOf)).toEqual(SHARED_KINDS);
  });

  test("pluralises a kind the page has no route for just the same", () => {
    // A hypothetical fourth vocabulary's row, were the table ever to list one before route.ts
    // knew about it, still has to read as something in its column.
    expect(vocabularyOf("widget")).toBe("widgets");
  });

  test("a word settles on the vocabulary it names", () => {
    expect(kindNamed("sections")).toBe("section");
    expect(kindNamed("constants")).toBe("constant");
    expect(kindNamed("rasters")).toBe("raster");
  });

  test("a word naming none of them settles on nothing, rather than on the first", () => {
    // The chooser takes any text typed. "section" is the singular, which no vocabulary is known
    // by here, and "widgets" is a vocabulary the tab does not hold at all: both leave the chooser
    // unset rather than guessing.
    expect(kindNamed("section")).toBeUndefined();
    expect(kindNamed("widgets")).toBeUndefined();
    expect(kindNamed("")).toBeUndefined();
  });
});

describe("a section's own two accesses", () => {
  test("are the model's, read-write first", () => {
    expect(SECTION_ACCESSES).toEqual(["read-write", "read-only"]);
  });
});

describe("what the add form is called", () => {
  test("names the vocabulary the chooser is on", () => {
    expect(addTitle("constant")).toBe("Declare a constant");
    expect(addTitle("section")).toBe("Declare a section");
  });

  test("names none while the chooser is unset", () => {
    expect(addTitle(undefined)).toBe("Declare an entry");
  });
});

describe("the key a row is selected by", () => {
  test("carries the row back whole, whichever vocabulary it belongs to", () => {
    expect(selectionAt(rowKey("section", ".calib"))).toEqual({ kind: "section", name: ".calib" });
    expect(selectionAt(rowKey("constant", "TREND_SAMPLES"))).toEqual({
      kind: "constant",
      name: "TREND_SAMPLES",
    });
    expect(selectionAt(rowKey("raster", "10ms"))).toEqual({ kind: "raster", name: "10ms" });
  });

  test("tells two rows of one spelling apart", () => {
    // The collision this key exists for. Both rows of ONE_SPELLING are declared, each under its
    // own kind, and a key of the name alone would have given them one id - `shared_rows` sorts by
    // kind then name, so the constant's row would always have answered for both.
    expect(isDeclared(ONE_SPELLING, "constant", "FOO")).toBe(true);
    expect(isDeclared(ONE_SPELLING, "section", "FOO")).toBe(true);
    expect(rowKey("constant", "FOO")).not.toBe(rowKey("section", "FOO"));
    expect(selectionAt(rowKey("section", "FOO"))).toEqual({ kind: "section", name: "FOO" });
    expect(selectionAt(rowKey("constant", "FOO"))).toEqual({ kind: "constant", name: "FOO" });
  });

  test("a row of a kind no address can name comes back as no selection", () => {
    // A vocabulary the tab does not hold at all - a fourth one, were it to exist - leaves the
    // address bare rather than opening another vocabulary's.
    expect(selectionAt(rowKey("widget", "10ms"))).toBeUndefined();
  });

  test("a key with no vocabulary in it is no selection either", () => {
    expect(selectionAt("FOO")).toBeUndefined();
  });

  test("splits at the first space, so a name holding one would still come back whole", () => {
    expect(selectionAt("section .a b")).toEqual({ kind: "section", name: ".a b" });
  });
});

describe("the json text a section's key travels as", () => {
  test("a string key goes in its quotes", () => {
    expect(sectionRaw("access", "read-only")).toBe('"read-only"');
    expect(sectionRaw("description", "calibration flash")).toBe('"calibration flash"');
  });

  test("alignment goes without them - quoted, it is a string the file's loader refuses", () => {
    expect(sectionRaw("alignment", "8")).toBe("8");
  });

  test("a set request quotes by the very key it carries", () => {
    // What the panel's own `satisfies` clause cannot say: that the key reaching the request is the
    // key that decided the quoting. Spelled twice, the two could be spelled differently - measured
    // in fix round 1, `sectionRaw("access", draftAlignment)` under the alignment request passed
    // every gate this repo has and sent `?raw="8"` for an alignment.
    expect(sectionSet(".calib", "alignment", "8")).toEqual({
      action: "set",
      name: ".calib",
      key: "alignment",
      raw: "8",
    });
    expect(sectionSet(".calib", "access", "read-only")).toEqual({
      action: "set",
      name: ".calib",
      key: "access",
      raw: '"read-only"',
    });
    expect(sectionSet(".calib", "description", "calibration flash")).toEqual({
      action: "set",
      name: ".calib",
      key: "description",
      raw: '"calibration flash"',
    });
  });
});

describe("the json text a raster's key travels as", () => {
  test("a string key goes in its quotes", () => {
    expect(rasterRaw("cycle", "10ms")).toBe('"10ms"');
    expect(rasterRaw("description", "the 10 ms control task")).toBe('"the 10 ms control task"');
  });

  test("event goes without them - quoted, it is a string the file's loader refuses", () => {
    expect(rasterRaw("event", "1")).toBe("1");
  });

  test("a set request quotes by the very key it carries", () => {
    // As `sectionSet`'s own case pins: the key reaching the request is the key that decided the
    // quoting, for each of a raster's three keys.
    expect(rasterSet("10ms", "event", "1")).toEqual({
      action: "set",
      name: "10ms",
      key: "event",
      raw: "1",
    });
    expect(rasterSet("10ms", "cycle", "20ms")).toEqual({
      action: "set",
      name: "10ms",
      key: "cycle",
      raw: '"20ms"',
    });
    expect(rasterSet("10ms", "description", "the 10 ms control task")).toEqual({
      action: "set",
      name: "10ms",
      key: "description",
      raw: '"the 10 ms control task"',
    });
  });
});

describe("declaring a constant", () => {
  test("asks for nothing until both a name and a value are typed", () => {
    expect(constantAdd("", "12")).toBeNull();
    expect(constantAdd("TREND_SLOTS", "")).toBeNull();
  });

  test("a field holding only spaces is a field not filled in, each on its own", () => {
    // One field at a time, so that each `.trim()` is pinned by a case of its own: both dropped
    // together still failed the joint case this replaces, and either dropped alone survived it.
    expect(constantAdd(" ", "12")).toBeNull();
    expect(constantAdd("TREND_SLOTS", " ")).toBeNull();
  });

  test("carries the name and the value as add takes them", () => {
    expect(constantAdd("TREND_SLOTS", "12")).toEqual({
      action: "add",
      name: "TREND_SLOTS",
      raw: "12",
    });
  });
});

describe("declaring a section", () => {
  test("asks for nothing until all three of its fields hold something", () => {
    expect(sectionAdd("", "read-write", "4")).toBeNull();
    expect(sectionAdd(".eol_log", "", "4")).toBeNull();
    expect(sectionAdd(".eol_log", "read-write", "")).toBeNull();
  });

  test("a field holding only spaces is a field not filled in, each on its own", () => {
    // One field at a time, as a constant's above: a reader who types a space into Alignment and
    // nothing else would otherwise be sent to the api and shown `bad-request` mid-keystroke,
    // which is the whole reason this function answers null.
    expect(sectionAdd(" ", "read-write", "4")).toBeNull();
    expect(sectionAdd(".eol_log", " ", "4")).toBeNull();
    expect(sectionAdd(".eol_log", "read-write", " ")).toBeNull();
  });

  test("carries its two required keys as json text, the access in its quotes", () => {
    // The trap this pins: `access` and `alignment` are judged as json, so an access sent bare
    // is refused and an alignment sent quoted declares a string the model will not load.
    expect(sectionAdd(".eol_log", "read-write", "8")).toEqual({
      action: "add",
      name: ".eol_log",
      access: '"read-write"',
      alignment: "8",
    });
  });
});

describe("why a section cannot be removed", () => {
  test("counts the definitions placing data in it", () => {
    expect(sectionRemoveBlocked(".fast_ram", 3)).toBe(
      "3 definitions place data in .fast_ram, so it cannot be removed.",
    );
  });

  test("says one of them in the singular, verb and all", () => {
    // Two plurals in one sentence, and "1 definition places" is not a substring of the other
    // spelling: `toBe` on the whole line is what catches a mutation that only pluralises one.
    expect(sectionRemoveBlocked(".calib", 1)).toBe(
      "1 definition places data in .calib, so it cannot be removed.",
    );
  });
});

describe("a plan's changes, ready to send", () => {
  const PLAN: PlanReply = {
    revision: 3,
    changes: [
      {
        file: "C:/w/constants.ddd.json",
        fingerprint: "a",
        operations: [{ op: "set", pointer: "constants[0].value", raw: "8" }],
        hunks: [{ line: 4, before: ['    "value": "16"'], after: ['    "value": "8"'] }],
      },
    ],
  };

  test("delegates to the units tab's converter - a plan is a plan whichever route previewed it", () => {
    expect(planEdit(PLAN, "the value of CELLS")).toEqual({
      changes: [
        {
          file: "C:/w/constants.ddd.json",
          fingerprint: "a",
          operations: [{ op: "set", pointer: "constants[0].value", raw: "8" }],
        },
      ],
      label: "the value of CELLS",
    });
  });

  test("a plan with nothing to change comes to no edit", () => {
    expect(planEdit({ revision: 3, changes: [] }, "the value of CELLS")).toBeNull();
  });
});
