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
