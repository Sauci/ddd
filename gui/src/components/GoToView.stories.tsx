import { useState } from "react";
import type { NamesReply } from "../api/types";
import { GoToView } from "./GoToView";

export default { title: "Components / GoToView" };

/** What `GET /api/names` answers of `C005` over a large project: fifty of the 2,250 names holding
 * it, C00500's outputs first, each opening on the component producing it. */
const C005: NamesReply = {
  revision: 3,
  total: 2250,
  names: Array.from({ length: 50 }, (_, index) => {
    const component = `C${String(500 + Math.floor(index / 15)).padStart(5, "0")}`;
    return {
      name: `${component}_O${String(index % 15).padStart(4, "0")}`,
      kind: "measurement",
      file: `C:/work/large/components/${component.toLowerCase()}.ddd.json`,
      component,
    };
  }),
};

/** The go-to with `typed` in it and the server's answer listed, the list opened on focus. */
function View({
  typed: initially,
  reply,
  note,
}: {
  typed: string;
  reply?: NamesReply;
  note?: string;
}) {
  const [typed, setTyped] = useState(initially);
  return (
    <GoToView
      typed={typed}
      onTyped={setTyped}
      reply={reply}
      onGo={() => undefined}
      onClose={() => setTyped("")}
      note={note}
      isDisabled={false}
      opened={reply !== undefined}
    />
  );
}

/** Nothing typed: the field alone, as the masthead draws it. */
export const Empty = () => <View typed="" />;

/** `C005` typed: fifty names, the kind of each and the component it opens on, and the line at the
 * list's foot saying how many more hold the text. */
export const Listing = () => <View typed="C005" reply={C005} />;

/** A project the analysis could not index: the server's refusal under the field. */
export const Refused = () => (
  <View typed="Speed" note="p.ddd.json did not load, so no variable of the project can be found" />
);
