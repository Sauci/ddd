import { describe, expect, test } from "vitest";
import type { PlanReply, SharedEntry, SharedReply } from "../api/types";
import {
  addTitle,
  constantAdd,
  isDeclared,
  kindNamed,
  kindOf,
  planEdit,
  SECTION_ACCESSES,
  SHARED_KINDS,
  SHARED_VOCABULARIES,
  sectionAdd,
  sectionRaw,
  sectionRemoveBlocked,
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

/** A table of rows of the kinds given, named `.a`, `.b`, ... so a row is told apart by name alone
 * whichever kind it carries - what `kindOf` is asked to answer from. */
function mixed(kinds: string[]): SharedReply {
  return {
    revision: 1,
    entries: kinds.map((kind, index) => ({
      kind,
      name: `.${String.fromCharCode(97 + index)}`,
      states: "x",
      uses: 0,
      findings: 0,
    })),
  };
}

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
  test("offers both, constants first - the order the server walks and sorts them in", () => {
    expect(SHARED_VOCABULARIES).toEqual(["constant", "section"]);
  });

  test("names each by its plural, which is also its file's own word", () => {
    expect(SHARED_VOCABULARIES.map(vocabularyOf)).toEqual(SHARED_KINDS);
  });

  test("pluralises a kind the page has no route for just the same", () => {
    // A row of a vocabulary the tab lists before it has a panel for it - a raster's, next part -
    // still has to read as something in its column.
    expect(vocabularyOf("raster")).toBe("rasters");
  });

  test("a word settles on the vocabulary it names", () => {
    expect(kindNamed("sections")).toBe("section");
    expect(kindNamed("constants")).toBe("constant");
  });

  test("a word naming none of them settles on nothing, rather than on the first", () => {
    // The chooser takes any text typed. "section" is the singular, which no vocabulary is known
    // by here, and "rasters" is a vocabulary the tab cannot declare into yet: both leave the
    // chooser unset rather than guessing.
    expect(kindNamed("section")).toBeUndefined();
    expect(kindNamed("rasters")).toBeUndefined();
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

describe("which vocabulary a selected row belongs to", () => {
  test("reads the row's own kind, not the name's spelling", () => {
    const table = mixed(["constant", "section"]);
    expect(kindOf(table, ".a")).toBe("constant");
    expect(kindOf(table, ".b")).toBe("section");
  });

  test("a name the table does not hold belongs to none", () => {
    // A rename's new spelling, in the moment before the table has been read again: the address
    // goes bare rather than to the panel of whichever vocabulary happened to be first.
    expect(kindOf(mixed(["section"]), ".calib")).toBeUndefined();
  });

  test("a kind no address can name belongs to none", () => {
    expect(kindOf(mixed(["raster"]), ".a")).toBeUndefined();
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
});

describe("declaring a constant", () => {
  test("asks for nothing until both a name and a value are typed", () => {
    expect(constantAdd("", "12")).toBeNull();
    expect(constantAdd("TREND_SLOTS", "")).toBeNull();
    expect(constantAdd("  ", " ")).toBeNull();
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
