import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback } from "react";
import { getSession } from "../api/client";
import { hrefOf, type ProjectView, type Route } from "../lib/route";
import type { SharedKind } from "../lib/shared";
import { ComparePage } from "../screens/ComparePage";
import { ComponentPage } from "../screens/ComponentPage";
import { FilesPage } from "../screens/FilesPage";
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
import { UpdatingNote } from "../ui/UpdatingNote";
import { UpdatingContext } from "./updating";
import { useProjectState } from "./useProjectState";
import { useRoute } from "./useRoute";

/** The project screen's tabs, in the order they are shown. */
const PROJECT_VIEWS = [
  ["graph", "Graph"],
  ["table", "Table"],
  ["units", "Units"],
  ["types", "Types"],
  ["shared", "Shared files"],
  ["files", "Files"],
  ["findings", "Findings"],
  ["compare", "Compare"],
] as const;

/** Each tab's own address, written out one view at a time rather than built from it: `PROJECT_
 * VIEWS.map()` below reads `view` widened to the union of all eight tab literals, and passing
 * that union straight to `hrefOf`/`navigate` stopped type-checking the moment one literal -
 * `shared` - came to name more than one of `Route`'s own shapes (a discriminant with more than
 * one shape behind a value stops the checker from trying each shape in turn). Spelling every key
 * here, instead of asserting the widened union as a `Route`, means a `ProjectView` whose bare
 * route ever needs more than `{ page, view }` fails to compile right here - which is exactly what
 * `shared` needing `kind`/`name` for its other shape would have hidden behind a cast, rather than
 * a wrong `Route` reaching `navigate` at runtime. The `Record<ProjectView,
 * Route>` annotation is what keeps `BARE_ROUTES[view]` typed as `Route` at the call sites below;
 * the `satisfies` clause beside it is what stops an entry naming a view other than its own key -
 * `Record` alone accepts `table`'s route under `graph` just as readily, a mistake nothing else
 * here would catch. */
const BARE_ROUTES: Record<ProjectView, Route> = {
  graph: { page: "project", view: "graph" },
  table: { page: "project", view: "table" },
  units: { page: "project", view: "units" },
  types: { page: "project", view: "types" },
  shared: { page: "project", view: "shared" },
  files: { page: "project", view: "files" },
  findings: { page: "project", view: "findings" },
  compare: { page: "project", view: "compare" },
} satisfies { [K in ProjectView]: { page: "project"; view: K } };

export function App() {
  const queries = useQueryClient();
  const [route, navigate] = useRoute();
  const session = useQuery({ queryKey: ["session"], queryFn: () => getSession() });
  const opened = session.data?.project ?? null;
  const { state, updating, stopped, failure } = useProjectState(opened !== null);
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
  // Selecting a shared entry replaces the address, as selecting a type does. The address carries
  // the vocabulary beside the name, because the tab holds three and a name alone cannot say which
  // one a reader picked; what it does not carry is whether that entry is declared. `SharedPage`
  // decides that itself, from `isDeclared` (design §2, "one route kind, and the page decides"),
  // so one address shape serves both the entry's own panel and the add form pre-filled with a
  // name nothing declares - this callback, the two `onOpenConstant` callbacks below and `routeOf`
  // (`lib/findings.ts`) all write that one shape. Those two name `constant` because that is what
  // a dimension names, not because the tab has one vocabulary; this one is told which kind the
  // row it came from carries. One address is unreachable as a result: `SharedPage`'s own blank
  // form, opened only by its Declare an entry button, has no route of its own and so does not
  // survive a reload the way every other panel on this page does. A pre-filled form is not
  // affected - it opens through the same address a declared name's own panel does.
  const openShared = useCallback(
    (name: string | undefined, kind: SharedKind | undefined) =>
      navigate(
        name === undefined || kind === undefined
          ? { page: "project", view: "shared" }
          : { page: "project", view: "shared", kind, name },
        { replace: true },
      ),
    [navigate],
  );
  // Selecting a row replaces the address, as selecting a shared entry does.
  const openFiles = useCallback(
    (path: string | undefined) =>
      navigate(
        path === undefined
          ? { page: "project", view: "files" }
          : { page: "project", view: "files", path },
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
          {/* Last in the row: coming and going, it moves none of the controls before it. */}
          {updating && <UpdatingNote />}
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
        {/* No tab asks the server anything before the project's first analysis has landed: each
            would be refused, and the graph would be asked for once more with no revision. */}
        {state === null ? (
          <p className="quiet">Analysing the project…</p>
        ) : route.view === "graph" ? (
          <GraphPage
            project={opened.path}
            state={state}
            variable={route.variable}
            stopped={stopped}
            onComponent={openComponent}
            onVariable={openVariable}
            onOpenType={(type) => navigate({ page: "project", view: "types", type })}
            onOpenConstant={(name) =>
              navigate({ page: "project", view: "shared", kind: "constant", name })
            }
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
            kind={"kind" in route ? route.kind : undefined}
            onName={openShared}
            stopped={stopped}
            onOpen={navigate}
          />
        ) : route.view === "files" ? (
          <FilesPage state={state} path={route.path} onPath={openFiles} stopped={stopped} />
        ) : route.view === "findings" ? (
          <FindingsPage state={state} stopped={stopped} onOpen={navigate} />
        ) : route.view === "compare" ? (
          <ComparePage state={state} stopped={stopped} onOpen={navigate} />
        ) : (
          <ProjectPage state={state} onComponent={openComponent} />
        )}
      </section>
    );
  } else if (state === null) {
    // A component's page, or its values, before the project's first analysis: named by the
    // project, the one name known yet, and nothing of the file asked for until there is one.
    page = (
      <section>
        <div className="heading">
          <h1>{opened.name ?? opened.path}</h1>
          {updating && <UpdatingNote />}
        </div>
        <p className="quiet">Analysing the project…</p>
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
        onOpenConstant={(name) =>
          navigate({ page: "project", view: "shared", kind: "constant", name })
        }
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
      {/* Every screen reads whether the findings may be about to change from here, and says so
          where its findings are (spec 6). */}
      <UpdatingContext value={updating}>
        <main>{page}</main>
      </UpdatingContext>
    </div>
  );
}
