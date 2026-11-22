import { useId } from "react";

interface Props {
  /** What the field is called, and what it reads while it is empty: `Filter components`. */
  label: string;
  value: string;
  onChange: (text: string) => void;
  /** What the filter leaves, beside the field (`filterLine`, lib/filter.ts); `null` while nothing
   * is typed. */
  line: string | null;
}

/**
 * The field that filters the table under it (16:I14), and the line beside it saying how many rows
 * it leaves of how many. The line is the field's description, and a status: a screen reader hears
 * each count as it changes. The line is drawn whether or not anything is typed, empty while
 * nothing is: a status is announced as it changes only where it was in the document before.
 */
export function FilterField({ label, value, onChange, line }: Props) {
  const described = useId();
  return (
    <div className="filter">
      <input
        // A textbox, as the Graph's search is: the role an <input type="text"> has.
        type="text"
        aria-label={label}
        placeholder={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby={described}
      />
      <span id={described} className="filter-line" role="status">
        {line ?? ""}
      </span>
    </div>
  );
}
