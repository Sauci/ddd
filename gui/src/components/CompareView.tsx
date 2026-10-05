import type { CompareReply, State } from "../api/types";
import { compareRouteReason, compareRows } from "../lib/compare";
import { countsOf, findingCounts, routeHref, routeLabel, routeOf } from "../lib/findings";
import type { Route } from "../lib/route";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { CompareTableView } from "./CompareTableView";
import { FindingPanelView } from "./FindingPanelView";

export interface CompareViewProps {
  /** The open project as the session last published it: what a finding that names a place in it
   * is routed against, exactly as the Findings tab routes its own (`routeLabel`,
   * `noRouteReason`). */
  state: State;
  /** Following a finding that names a place in the open project, which the app navigates to. */
  onOpen: (route: Route) => void;
  /** What the field shows: typed freely, and asked for only once the reader submits it - changing
   * it never asks again on its own. */
  baseline: string;
  onBaseline: (path: string) => void;
  /** Submitting the field: compares the open project against `baseline` as it now reads. */
  onAsk: () => void;
  /** The last comparison the server answered, or `null` before the reader has asked, or while a
   * refused ask has cleared it. */
  reply: CompareReply | null;
  /** Why the last ask was refused, or `null`. */
  refusal: string | null;
  /** Asking, or the server stopped: the field and its button take no input. */
  busy: boolean;
  /** The key of the finding row whose panel is open, or `undefined` - `CompareTableView` and
   * `FindingPanelView`'s own pairing, as the Findings tab holds its own (`FindingsPage`). */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

/**
 * The Compare tab (spec 2026-09-26-gui-compare-design.md §6): can the open project replace a
 * baseline delivery? A picture of its props, drawn in the order the spec gives - the field, the
 * verdict leading, the findings below it, the renames as a table, and a refused baseline's
 * reason.
 *
 * A finding that names a place in the open project leads there, through the same `routeOf`
 * family the Findings tab uses: a plugin's comparison rule files at the declaration it is about
 * - `layout/key-changed` at `component.interface[0]` of the component that declares the entry -
 * and there is no reason to make a reader hunt for a place the finding already names. Most rows
 * still lead nowhere, and `../lib/compare`'s `compareRouteReason` says which of the three kinds
 * of row it is looking at; `FindingPanelView` draws the reason only where there is no link.
 * Routing a finding by the *object its message names*, rather than by the place it is filed at,
 * is still a part of its own (spec §5): a `renamed-object` names two objects and neither is
 * where it sits.
 *
 * `reply.findings` and `reply.baseline_findings` are two fields on purpose (`CompareReply`'s own
 * docstrings), not one a page would have to sort back apart by matching a message's own text -
 * `compareRows` reads which is which structurally and carries it onto every row, which is what
 * lets the File column name a baseline row as the baseline's own even when its file displays
 * with the very name one of the candidate's own files has.
 */
export function CompareView(props: CompareViewProps) {
  const { reply, refusal, busy } = props;
  const rows = reply === null ? [] : compareRows(reply);
  const row = rows.find((entry) => entry.key === props.selected);
  return (
    <>
      <div className="compare-field">
        <label className="panel-field">
          Baseline
          <input
            type="text"
            value={props.baseline}
            disabled={busy}
            onChange={(event) => props.onBaseline(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && props.baseline.trim() !== "") props.onAsk();
            }}
          />
        </label>
        {/* The reach, in the words that are true of it: the root is the directory `ddd gui` was
            started in - `Session(Path.cwd(), ...)` - which may be far above the open project, and
            "this project's own root" told the reader it was narrower than it is. `holds_a_description`
            answers for a component file too, so one is a baseline of its own and the sentence says
            so rather than offering less than the field takes. */}
        <p className="quiet">
          Accepts a dumped dictionary, or a project or component description, at a path under the
          directory ddd gui was started in.
        </p>
        <Button
          variant="primary"
          isDisabled={busy || props.baseline.trim() === ""}
          onPress={props.onAsk}
        >
          Compare
        </Button>
      </div>
      {reply !== null && (
        <>
          <p className={reply.verdict ? "verdict pass" : "verdict fail"} role="status">
            {reply.verdict
              ? "This project can replace the baseline."
              : "This project cannot replace the baseline."}
          </p>
          <p className="summary">
            {findingCounts(countsOf(rows.map((entry) => entry.finding)), false)}
          </p>
          <div className={row !== undefined ? "with-panel" : undefined}>
            <div>
              <CompareTableView rows={rows} selected={props.selected} onSelect={props.onSelect} />
            </div>
            {row !== undefined && (
              <div key={props.selected}>
                <FindingPanelView
                  finding={row.finding}
                  label={routeLabel(row.finding, props.state)}
                  href={routeHref(row.finding)}
                  reason={compareRouteReason(row, props.state)}
                  onOpen={() => {
                    const route = routeOf(row.finding);
                    if (route !== null) props.onOpen(route);
                  }}
                  // Nothing here ever offers a fix: `POST /api/edit` changes the open project,
                  // and a comparison's own finding names no place in it to change (see `reason`
                  // above), while a baseline's finding is not about the open project at all.
                  fixes={null}
                  chosen={undefined}
                  onChoose={() => {}}
                  changesShown={false}
                  onChangesShown={() => {}}
                  onApply={() => {}}
                  refusal={null}
                  busy={busy}
                  onClose={() => props.onSelect(undefined)}
                />
              </div>
            )}
          </div>
          <h2 className="panel-heading">Renamed objects</h2>
          <p className="rename-note">
            A calibration dataset, a recording or a test script keyed by the old spelling needs this
            to find the same object under its new name.
          </p>
          {reply.renames.length === 0 ? (
            <p className="quiet">Nothing was renamed.</p>
          ) : (
            <table className="panel-declarations">
              <thead>
                <tr>
                  <th scope="col">Id</th>
                  <th scope="col">From</th>
                  <th scope="col">To</th>
                </tr>
              </thead>
              <tbody>
                {reply.renames.map((renamed) => (
                  <tr key={renamed.id}>
                    <td className="quiet">{renamed.id}</td>
                    <td>{renamed.old}</td>
                    <td>{renamed.new}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
      {refusal !== null && <Banner tone="error">{refusal}</Banner>}
    </>
  );
}
