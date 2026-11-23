import { describe, expect, test } from "vitest";
import type { NamedVariable, NamesReply } from "../api/types";
import {
  entered,
  FINDING_NAMES,
  GO_TO,
  goToList,
  goToRoute,
  NO_NAME,
  noName,
  ownAnswer,
} from "./goTo";

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
    expect(noName([])).toBe(NO_NAME);
  });

  test("says no variable of a file that loaded matches while a file did not, naming it", () => {
    // A name only that file declares is in no index (B11-28): "no variable matches" was false of
    // it, as a removal's "no other component declares" was (16:I10). Named as the banner under the
    // masthead names them.
    const unread = ["controller.ddd.json"];
    expect(noName(unread)).toBe(
      "no variable of a file that loaded matches, and controller.ddd.json did not load",
    );
    expect(goToList({ revision: 3, total: 0, names: [] }, "ParameterA", false, unread)).toEqual({
      sections: [],
      footnote: undefined,
      empty: noName(unread),
    });
    expect(goToList(REPLY, "C00530", false, unread).empty).toBe(noName(unread));
    expect(noName(["a.ddd.json", "b.ddd.json"])).toBe(
      "no variable of a file that loaded matches, and a.ddd.json and b.ddd.json did not load",
    );
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

describe("Enter in the masthead's go-to", () => {
  /** What `GET /api/names` answers of `C`, the first text asked: fifty names, none of C00530. */
  const FIRST: NamesReply = { revision: 3, total: 20000, names: [named("C00000_O0000", "C00000")] };

  test("goes at once where the answer in hand holds the name, an earlier text's included", () => {
    const route = {
      page: "component",
      file: "C:/work/large/components/c00530.ddd.json",
      variable: "C00530_O0000",
    };
    expect(entered("C00530_O0000", REPLY, REPLY)).toEqual({ go: route });
    // The answer of `C00530` kept listed while `C00530_O0000`'s own is asked: it holds the name.
    expect(entered("C00530_O0000", REPLY, undefined)).toEqual({ go: route });
  });

  test("waits for the text's own answer where the answer in hand is another's, without it", () => {
    expect(entered("C00530_O0000", FIRST, undefined)).toBe("ask");
    expect(entered("C00530_O0000", undefined, undefined)).toBe("ask");
  });

  test("opens the list where the text's own answer does not spell the name, its case included", () => {
    expect(entered("c00530_o0000", REPLY, REPLY)).toBe("list");
    const none: NamesReply = { revision: 3, total: 0, names: [] };
    expect(entered("nothing like it", none, none)).toBe("list");
  });

  test("does nothing in a field holding nothing", () => {
    expect(entered("", REPLY, REPLY)).toBeNull();
    expect(entered("   ", undefined, undefined)).toBeNull();
  });

  test("takes an answer as the text's own once it is no earlier text's, asked for this text", () => {
    expect(ownAnswer(REPLY, false, "C00530", "C00530")).toBe(REPLY);
    // Asked for the text without the white space around it, as the field's text is asked for.
    expect(ownAnswer(REPLY, false, "C00530", " C00530 ")).toBe(REPLY);
  });

  test("takes no answer as the text's own while it is an earlier text's, or another text's", () => {
    // Kept listed while the text's own is asked (TanStack Query's placeholder).
    expect(ownAnswer(REPLY, true, "C00530", "C00530")).toBeUndefined();
    // Asked for the text before: typing has not paused since.
    expect(ownAnswer(REPLY, false, "C0053", "C00530")).toBeUndefined();
    expect(ownAnswer(undefined, false, "C00530", "C00530")).toBeUndefined();
  });
});
