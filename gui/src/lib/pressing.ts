/**
 * What a press of a table's row is for (16:M21): opening what the row leads to - its component's
 * page, its panel - or, where the reader dragged over the words of its cells, selecting them, a
 * path or a message to copy, which a panel's words always allowed. What the page finds of the
 * press and the document's selection is gathered by `ui/Table.tsx`, and judged here.
 */

/** What the page finds as a press of a table's row ends. */
export interface PressEnd {
  /** A selection began while the press lasted: it went down on the words of the row's cells, as a
   * drag over them starts one - and as a click does, leaving the caret where it went down - or a
   * double click picked a word. A press of a button of the row begins none. */
  began: boolean;
  /** The document's selection holds words now, every one of them in the row pressed. */
  selected: boolean;
}

/** Whether a press of a row that ends as `end` says was the reader selecting the words of its
 * cells: a selection begun with the press, which holds words of that row as it ends. Such a press
 * opens nothing, the row's action and its selection alike - the words it selected, to be copied,
 * are what it was for. A click is the row's own, the caret it leaves holding no words, and so is a
 * press that began no selection: a button of the row pressed while words the reader selected
 * before still stand in it. */
export function selectsText(end: PressEnd): boolean {
  return end.began && end.selected;
}
