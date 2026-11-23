import { PROJECT_VIEWS, VIEW_NAMES } from "../lib/announcing";
import { tabHref } from "../lib/route";
import { LinkTabs } from "./LinkTabs";

export default { title: "UI / LinkTabs" };

export const GraphOpen = () => (
  <LinkTabs
    label="Project views"
    tabs={[
      { href: "/project", label: "Graph", current: true, onFollow: () => undefined },
      { href: "/project?view=table", label: "Table", current: false, onFollow: () => undefined },
    ]}
  />
);

/** The project screen's eight tabs in a window 375px wide, the page's own padding aside: they wrap
 * onto a second line rather than reach past its edge (16:M9). */
export const Narrow = () => (
  <div style={{ width: 343 }}>
    <LinkTabs
      label="Project views"
      tabs={PROJECT_VIEWS.map((view) => ({
        href: tabHref(view),
        label: VIEW_NAMES[view],
        current: view === "graph",
        onFollow: () => undefined,
      }))}
    />
  </div>
);
