import { describe, expect, test } from "vitest";
import {
  describeRequest,
  describeSentence,
  descriptionIn,
  descriptionShown,
  EDITED_ELSEWHERE,
} from "./description";

/** A component file as `GET /api/file` parses it: ParameterA states its description, ValueC states
 * none, and Odd states one that is no text. */
const COMPONENT = {
  component: {
    name: "Controller",
    interface: [
      {
        scope: "local",
        definition: { name: "ParameterA", description: "Single calibratable constant" },
      },
      { scope: "output", definition: { name: "ValueC" } },
      { scope: "output", definition: { name: "Odd", description: 3 } },
    ],
  },
};

describe("descriptionIn", () => {
  test("is what the declaration states", () => {
    expect(descriptionIn(COMPONENT, "ParameterA")).toBe("Single calibratable constant");
  });

  test("is the empty text where the declaration states none", () => {
    expect(descriptionIn(COMPONENT, "ValueC")).toBe("");
  });

  test("is the empty text where what it states is no text", () => {
    expect(descriptionIn(COMPONENT, "Odd")).toBe("");
  });

  test("is nothing where the file declares no such variable", () => {
    expect(descriptionIn(COMPONENT, "Nope")).toBeNull();
  });

  test("is nothing for a file with no interface, or none that parsed", () => {
    expect(descriptionIn({ project: { name: "P" } }, "ParameterA")).toBeNull();
    expect(descriptionIn(null, "ParameterA")).toBeNull();
  });
});

describe("descriptionShown", () => {
  test("is what was typed, the empty text included", () => {
    expect(descriptionShown("new", "old")).toBe("new");
    expect(descriptionShown("", "old")).toBe("");
  });

  test("is the file's own while nothing is typed", () => {
    expect(descriptionShown(undefined, "old")).toBe("old");
  });
});

describe("describeRequest", () => {
  const asked = { file: "/p/c.ddd.json", name: "ParameterA" };

  test("asks for what was typed, the empty text included, which takes the key away", () => {
    expect(describeRequest(asked, "new words", "old")).toEqual({
      ...asked,
      description: "new words",
    });
    expect(describeRequest(asked, "", "old")).toEqual({ ...asked, description: "" });
  });

  test("asks for nothing while nothing is typed", () => {
    expect(describeRequest(asked, undefined, "old")).toBeNull();
  });

  test("asks for nothing of text typed back to the file's own", () => {
    expect(describeRequest(asked, "old", "old")).toBeNull();
  });

  test("asks for nothing without a file, which is the project screen's panel", () => {
    expect(describeRequest(undefined, "new", "old")).toBeNull();
  });
});

describe("describeSentence", () => {
  test("a description set names the declaration and its component", () => {
    expect(describeSentence("ParameterA", "Controller", "A gain")).toBe(
      "Sets the description of ParameterA in Controller",
    );
  });

  test("the empty text takes it out", () => {
    expect(describeSentence("ParameterA", "Controller", "")).toBe(
      "Takes the description of ParameterA out of Controller",
    );
  });
});

describe("EDITED_ELSEWHERE", () => {
  test("says what the panel does not do, and where it is done", () => {
    expect(EDITED_ELSEWHERE).toBe(
      "Renaming the variable and changing its scope are done in its file, in the editor.",
    );
  });
});
