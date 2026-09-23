import { Button } from "../ui/Button";
import { ComboBox } from "../ui/ComboBox";

export interface DimensionsFieldProps {
  /** One entry per dimension, each a whole number or a constant's name. */
  rows: string[];
  /** The project's constants, offered beside whatever is typed. */
  constants: string[];
  /** The name the labels speak of, so a screen reader hears which object this shapes. */
  owner: string;
  busy: boolean;
  onRows: (rows: string[]) => void;
}

/** A value block's shape: one `size` field per dimension, in c declaration order. A picture of
 * its props - it holds nothing of its own. */
export function DimensionsField({ rows, constants, owner, busy, onRows }: DimensionsFieldProps) {
  const shown = rows.length === 0 ? [""] : rows;
  return (
    // A div, not a fieldset: a fieldset's own border and padding would frame the rows, and
    // Task 6's panel wants only the boundary a screen reader needs, not a border of its own.
    // biome-ignore lint/a11y/useSemanticElements: see above
    <div className="dimensions-field" role="group" aria-label={`Dimensions of ${owner}`}>
      {shown.map((row, index) => (
        // The index is the identity here: a dimension has no name, and two of the same size
        // are two different dimensions of one shape.
        // biome-ignore lint/suspicious/noArrayIndexKey: a dimension is its position
        <div className="dimension-row" key={index}>
          <ComboBox
            label={`Dimension ${index + 1} of ${owner}`}
            inputValue={row}
            onInputChange={(value) => onRows(shown.map((old, at) => (at === index ? value : old)))}
            sections={[
              {
                id: "constants",
                title: "This project's constants",
                choices: constants.map(choiceOf),
              },
            ]}
            onPick={(id) => onRows(shown.map((old, at) => (at === index ? id : old)))}
            onEnter={(text) => onRows(shown.map((old, at) => (at === index ? text : old)))}
            onClose={() => undefined}
            isDisabled={busy}
          />
          <Button
            variant="link"
            aria-label={`Remove dimension ${index + 1} of ${owner}`}
            isDisabled={busy || shown.length === 1}
            onPress={() => onRows(shown.filter((_, at) => at !== index))}
          >
            Remove
          </Button>
        </div>
      ))}
      <Button variant="link" isDisabled={busy} onPress={() => onRows([...shown, ""])}>
        Add a dimension
      </Button>
    </div>
  );
}

function choiceOf(constant: string) {
  return { id: constant, label: constant, detail: "" };
}
