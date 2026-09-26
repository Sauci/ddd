import type { CompareReply } from "../api/types";
import { compareRouteReason } from "../lib/compare";
import { findingCounts, findingRows } from "../lib/findings";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { FindingPanelView } from "./FindingPanelView";
import { FindingsTableView } from "./FindingsTableView";

export interface CompareViewProps {
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
  /** The key of the finding row whose panel is open, or `undefined` - `FindingsTableView` and
   * `FindingPanelView`'s own pairing, exactly as the Findings tab holds it (`FindingsPage`). */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

/**
 * The Compare tab (spec 2026-09-26-gui-compare-design.md §6): can the open project replace a
 * baseline delivery? A picture of its props, drawn in the order the spec gives - the field, the
 * verdict leading, the findings below it, the renames as a table, and a refused baseline's
 * reason.
 *
 * Every finding this draws routes nowhere: `compare`'s own findings are filed on the candidate's
 * whole project rather than a place in one file, and the baseline's own are marked route-less at
 * the source regardless of where their path resolves to (`../lib/compare`'s own docstring has
 * the full reasoning). So, unlike the Findings tab this is otherwise the twin of, `label` and
 * `href` are given as `null` outright rather than asked of `../lib/findings`' `routeOf` family -
 * asking would answer the same `null`, every time, but would say so by re-deriving it from a
 * `State` this tab does not need for anything else. `onOpen` is never called for the same reason,
 * and stays a plain no-op: routing a comparison finding by the object it names is real work left
 * to a part of its own (spec §5), not a wire this tab pre-runs today.
 */
export function CompareView(props: CompareViewProps) {
  const { reply, refusal, busy } = props;
  const rows = reply === null ? [] : findingRows(reply.findings);
  const finding = rows.find((row) => row.key === props.selected)?.finding;
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
        <p className="quiet">
          Accepts a dumped dictionary or a project description, at a path under this project's own
          root.
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
          <p className="summary">{findingCounts(reply.findings)}</p>
          <div className={finding !== undefined ? "with-panel" : undefined}>
            <div>
              <FindingsTableView rows={rows} selected={props.selected} onSelect={props.onSelect} />
            </div>
            {finding !== undefined && (
              <div key={props.selected}>
                <FindingPanelView
                  finding={finding}
                  label={null}
                  href={null}
                  reason={compareRouteReason(finding)}
                  onOpen={() => {}}
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
