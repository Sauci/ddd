import { describe, expect, test } from "vitest";
import type { NamedVariable, NamesReply } from "../api/types";
import { FINDING_NAMES, GO_TO, goToList, goToRoute, NO_NAME } from "./goTo";

const named = (name: string, component: string, kind = "measurement"): NamedVariable => ({
  name,
  kind,
  file: `C:/work/large/components/${component.toLowerCase()}.ddd.json`,
  component,
});

/** What `GET /api/names` answers of `C00530`: two of its names, each opening on C00530. */
const REPLY: NamesReply = {
  revision: 3,
  total: 2,
  names: [named("C00530_O0000", "C00530"), named("C00530_O0001", "C00530", "parameter")],
};

/** A list closed: nothing typed, or a refusal said under the field. */
const CLOSED = { sections: [], footnote: undefined, empty: undefined };

describe("the masthead's go-to", () => {
  test("is called what it does", () => {
    expect(GO_TO).toBe("Go to a variable");
  });

  test("lists each name answered in the server's order, with its kind and its component", () => {
    expect(goToList(REPLY, "C00530", false)).toEqual({
      sections: [
        {
          id: "names",
          title: "This project's variables",
          choices: [
            { id: "C00530_O0000", label: "C00530_O0000", detail: "measurement in C00530" },
            { id: "C00530_O0001", label: "C00530_O0001", detail: "parameter in C00530" },
          ],
        },
      ],
      footnote: undefined,
      empty: NO_NAME,
    });
  });

  test("says how many more names hold the text than the server answered, and to type", () => {
    expect(goToList({ ...REPLY, total: 1172 }, "C005", false).footnote).toBe(
      "1,170 more names match: type to narrow the list.",
    );
    expect(goToList({ ...REPLY, total: 3 }, "C005", false).footnote).toBe(
      "1 more name matches: type to narrow the list.",
    );
  });

  test("opens on what is typed before any name has come, and says it is finding them", () => {
    // The names come from the server after the text is typed: React Aria opens a list on a text
    // only where the list holds entries then, unless it may be empty.
    expect(FINDING_NAMES).toBe("Finding names…");
    expect(goToList(undefined, "C005", false)).toEqual({
      sections: [],
      footnote: undefined,
      empty: FINDING_NAMES,
    });
  });

  test("says that no name holds the text, where none does", () => {
    expect(NO_NAME).toBe("no variable matches");
    expect(goToList({ revision: 3, total: 0, names: [] }, "nothing", false)).toEqual({
      sections: [],
      footnote: undefined,
      empty: NO_NAME,
    });
  });

  test("lists nothing, and stays closed, while nothing is typed or the server refused", () => {
    expect(goToList(REPLY, "", false)).toEqual(CLOSED);
    expect(goToList(REPLY, "   ", false)).toEqual(CLOSED);
    expect(goToList(undefined, "", false)).toEqual(CLOSED);
    // The refusal is said under the field: the list neither waits for names nor says none match.
    expect(goToList(undefined, "Speed", true)).toEqual(CLOSED);
    expect(goToList(REPLY, "C00530", true)).toEqual(CLOSED);
  });

  test("goes to a name's component, its panel open", () => {
    expect(goToRoute(REPLY, "C00530_O0001")).toEqual({
      page: "component",
      file: "C:/work/large/components/c00530.ddd.json",
      variable: "C00530_O0001",
    });
  });

  test("goes nowhere for a text no name answered spells exactly", () => {
    expect(goToRoute(REPLY, "C00530")).toBeNull();
    expect(goToRoute(REPLY, "c00530_o0000")).toBeNull();
    expect(goToRoute(undefined, "C00530_O0000")).toBeNull();
  });
});
