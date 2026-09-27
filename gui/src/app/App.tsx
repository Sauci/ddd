import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback } from "react";
import { getSession } from "../api/client";
import { hrefOf, type ProjectView, type Route } from "../lib/route";
import { ComparePage } from "../screens/ComparePage";
import { ComponentPage } from "../screens/ComponentPage";
import { FindingsPage } from "../screens/FindingsPage";
import { GraphPage } from "../screens/GraphPage";
import { ProjectPage } from "../screens/ProjectPage";
import { SharedPage } from "../screens/SharedPage";
import { StartPage } from "../screens/StartPage";
import { TypesPage } from "../screens/TypesPage";
import { UndoStrip } from "../screens/UndoStrip";
import { UnitsPage } from "../screens/UnitsPage";
import { ValuesPage } from "../screens/ValuesPage";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { LinkTabs } from "../ui/LinkTabs";
import { useProjectState } from "./useProjectState";
import { useRoute } from "./useRoute";

/** The project screen's tabs, in the order they are shown. */
const PROJECT_VIEWS = [
  ["graph", "Graph"],
  ["table", "Table"],
  ["units", "Units"],
  ["types", "Types"],
  ["shared", "Shared files"],
  ["findings", "Findings"],
  ["compare", "Compare"],
] as const;

/** Each tab's own address, written out one view at a time rather than built from it: `PROJECT_
 * VIEWS.map()` below reads `view` widened to the union of all seven tab literals, and passing
 * that union straight to `hrefOf`/`navigate` stopped type-checking the moment one literal -
 * `shared` - came to name more than one of `Route`'s own shapes (a discriminant with more than
 * one shape behind a value stops the checker from trying each shape in turn). Spelling every key
 * here, instead of asserting the widened union as a `Route`, means a `ProjectView` whose bare
 * route ever needs more than `{ page, view }` fails to compile right here - which is exactly what
 * `shared` needing `kind`/`name`/`declare` for its other two shapes would have hidden behind a
 * cast, rather than a wrong `Route` reaching `navigate` at runtime. */
const BARE_ROUTES: Record<ProjectView, Route> = {
  graph: { page: "project", view: "graph" },
  table: { page: "project", view: "table" },
  units: { page: "project", view: "units" },
  types: { page: "project", view: "types" },
  shared: { page: "project", view: "shared" },
  findings: { page: "project", view: "findings" },
  compare: { page: "project", view: "compare" },
};

export function App() {
  const queries = useQueryClient();
  const [route, navigate] = useRoute();
  const session = useQuery({ queryKey: ["session"], queryFn: () => getSession() });
  const opened = session.data?.project ?? null;
  const { state, stopped, failure } = useProjectState(opened !== null);
  // One identity for the whole life of the page: the canvas hands this to every module it draws,
  // and a new function each render would lay the canvas out again each render.
  const openComponent = useCallback(
    (file: string) => navigate({ page: "component", file }),
    [navigate],
  );
  // Also one stable identity: the canvas lays itself out again whenever the arrows' own click
  // and keyboard handlers change, and those close over this callback.
  const openVariable = useCallback(
    (variable: string | undefined) =>
      navigate(
        variable === undefined
          ? { page: "project", view: "graph" }
          : { page: "project", view: "graph", variable },
        { replace: true },
      ),
    [navigate],
  );
  // Selecting a unit replaces the address, as selecting a variable does.
  const openUnit = useCallback(
    (unit: string | undefined) =>
      navigate(
        unit === undefined
          ? { page: "project", view: "units" }
          : { page: "project", view: "units", unit },
        { replace: true },
      ),
    [navigate],
  );
  // Selecting a type replaces the address, as selecting a unit does.
  const openType = useCallback(
    (type: string | undefined) =>
      navigate(
        type === undefined
          ? { page: "project", view: "types" }
          : { page: "project", view: "types", type },
        { replace: true },
      ),
    [navigate],
  );
  // Selecting a constant replaces the address, as selecting a type does. The route's other shape,
  // naming one to declare, is Task 8's: SharedPage draws no panel for either yet, so this task
  // only ever writes the "declared" shape back.
  const openShared = useCallback(
    (name: string | undefined) =>
      navigate(
        name === undefined
          ? { page: "project", view: "shared" }
          : { page: "project", view: "shared", kind: "constant", name },
        { replace: true },
      ),
    [navigate],
  );

  let page: ReactNode;
  if (session.isPending) {
    page = <p className="quiet">Connecting…</p>;
  } else if (session.isError) {
    page = <Banner tone="error">{session.error.message}</Banner>;
  } else if (opened === null || route.page === "start") {
    page = (
      <StartPage
        onOpened={() => {
          void queries.invalidateQueries({ queryKey: ["session"] });
          navigate({ page: "project", view: "graph" });
        }}
      />
    );
  } else if (route.page === "project") {
    page = (
      <section>
        <div className="heading">
          <h1>{opened.name ?? opened.path}</h1>
          <UndoStrip state={state} stopped={stopped} />
        </div>
        <LinkTabs
          label="Project views"
          tabs={PROJECT_VIEWS.map(([view, label]) => ({
            href: hrefOf(BARE_ROUTES[view]),
            label,
            current: route.view === view,
            onFollow: () => navigate(BARE_ROUTES[view]),
          }))}
        />
        {route.view === "graph" ? (
          <GraphPage
            project={opened.path}
            state={state}
            variable={route.variable}
            stopped={stopped}
            onComponent={openComponent}
            onVariable={openVariable}
            onOpenType={(type) => navigate({ page: "project", view: "types", type })}
          />
        ) : route.view === "units" ? (
          <UnitsPage state={state} unit={route.unit} stopped={stopped} onUnit={openUnit} />
        ) : route.view === "types" ? (
          <TypesPage
            state={state}
            type={route.type}
            stopped={stopped}
            onType={openType}
            onOpen={navigate}
          />
        ) : route.view === "shared" ? (
          <SharedPage
            state={state}
            name={"name" in route ? route.name : undefined}
            onName={openShared}
          />
        ) : route.view === "findings" ? (
          <FindingsPage state={state} stopped={stopped} onOpen={navigate} />
        ) : route.view === "compare" ? (
          <ComparePage state={state} stopped={stopped} onOpen={navigate} />
        ) : (
          <ProjectPage state={state} onComponent={openComponent} />
        )}
      </section>
    );
  } else if ("view" in route) {
    // The values grid is its own page, not a panel this file's own screen can open in place: a
    // reader's address bar, a bookmark or a finding's link all reach it the same way.
    page = (
      <ValuesPage
        key={route.variable}
        name={route.variable}
        file={route.file}
        state={state}
        stopped={stopped}
        onBack={() => navigate({ page: "component", file: route.file })}
      />
    );
  } else {
    page = (
      <ComponentPage
        file={route.file}
        variable={route.variable}
        state={state}
        stopped={stopped}
        onVariable={(variable) =>
          navigate(
            variable === undefined
              ? { page: "component", file: route.file }
              : { page: "component", file: route.file, variable },
            { replace: true },
          )
        }
        onValues={(variable) =>
          navigate({ page: "component", file: route.file, variable, view: "values" })
        }
        onOpenType={(type) => navigate({ page: "project", view: "types", type })}
      />
    );
  }

  return (
    <div className="app">
      <header className="masthead">
        <span className="brand">ddd gui</span>
        <span className="preview">preview</span>
        <nav>
          <Button variant="link" onPress={() => navigate({ page: "start" })}>
            Projects
          </Button>
          {opened !== null && (
            <Button variant="link" onPress={() => navigate({ page: "project", view: "graph" })}>
              {opened.name ?? opened.path}
            </Button>
          )}
        </nav>
      </header>
      {stopped && (
        <Banner tone="error">
          ddd gui has stopped. Start it again and open the address it prints.
        </Banner>
      )}
      {failure !== null && <Banner tone="error">{failure}</Banner>}
      <main>{page}</main>
    </div>
  );
}
