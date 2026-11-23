import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useSyncExternalStore } from "react";
import { getSession } from "../api/client";
import { signedOut } from "../api/token";
import { LoadBannerView } from "../components/LoadBannerView";
import { SignedOutView } from "../components/SignedOutView";
import { UndrawnView } from "../components/UndrawnView";
import { type ProjectView, type Route, tabHref } from "../lib/route";
import { projectName, sessionAskedFor } from "../lib/session";
import type { SharedKind } from "../lib/shared";
import { undrawnSentence } from "../lib/undrawn";
import { loadBanner } from "../lib/unloaded";
import { beforeAnalysis } from "../lib/updating";
import { ComparePage } from "../screens/ComparePage";
import { ComponentPage } from "../screens/ComponentPage";
import { FilesPage } from "../screens/FilesPage";
import { FindingsPage } from "../screens/FindingsPage";
import { GoTo } from "../screens/GoTo";
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
import { UpdatingStatus } from "../ui/UpdatingNote";
import { ErrorBoundary } from "./ErrorBoundary";
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

/** Each tab's own route, written out one view at a time rather than built from it: `PROJECT_
 * VIEWS.map()` below reads `view` widened to the union of all eight tab literals, and passing
 * that union straight to `hrefOf`/`navigate` stopped type-checking the moment one literal -
 * `shared` - came to name more than one of `Route`'s own shapes (a discriminant with more than
 * one shape behind a value stops the checker from trying each shape in turn). Spelling every key
 * here, instead of asserting the widened union as a `Route`, means a `ProjectView` whose bare
 * route ever needs more than `{ page, view }` fails to compile right here - which is exactly what
 * `shared` needing `kind`/`name` for its other shape would have hidden behind a cast, rather than
 * a wrong `Route` reaching `navigate` at runtime. The `Record<ProjectView,
 * Route>` annotation is what keeps `BARE_ROUTES[view]` typed as `Route` at the call site below;
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
  const [route, navigate, arrived] = useRoute();
  const out = useSyncExternalStore(signedOut.subscribe, signedOut.current);
  const session = useQuery({ queryKey: ["session"], queryFn: () => getSession() });
  const opened = session.data?.project ?? null;
  const { state, project, failed, refused, updating, stopped, failure } = useProjectState(
    opened !== null,
  );
  // Asked again for each project the state followed comes to be of while the session names
  // another: another page of the same server opened it (`sessionAskedFor`, lib/session.ts). Keyed
  // by that project, so that a state moving on while an ask is out asks once more, cancelling the
  // ask before it, whose answer may name the project before.
  const askedFor = sessionAskedFor(opened, project);
  useEffect(() => {
    if (askedFor !== null) void queries.invalidateQueries({ queryKey: ["session"] });
  }, [askedFor, queries]);
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

  if (out)
    return (
      <div className="app">
        <SignedOutView />
      </div>
    );
  // What the tabs' place says before the first analysis has landed: that it is on its way, or
  // nothing once it failed, which the banner under the masthead says.
  const waiting = beforeAnalysis(failed);
  // The banner is the open project's, under the masthead of each of its pages - its tabs, a
  // component's and its values - and of no other: the start page lists the projects to open.
  const banner =
    session.isSuccess && opened !== null && route.page !== "start"
      ? loadBanner(project, state, failed, refused)
      : null;
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
          <h1>{projectName(opened, project)}</h1>
          <UndoStrip state={state} stopped={stopped} />
          {/* Last in the row, so that none of the controls before it ever moves. */}
          <UpdatingStatus updating={updating} />
        </div>
        <LinkTabs
          label="Project views"
          tabs={PROJECT_VIEWS.map(([view, label]) => ({
            href: tabHref(view),
            label,
            current: route.view === view,
            onFollow: () => navigate(BARE_ROUTES[view]),
          }))}
        />
        {/* No tab asks the server anything before the project's first analysis has landed: each
            would be refused, and the graph would be asked for once more with no revision. */}
        {state === null ? (
          waiting !== null && <p className="quiet">{waiting}</p>
        ) : route.view === "graph" ? (
          <GraphPage
            project={state.project}
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
          <FilesPage
            state={state}
            path={route.path}
            arrived={arrived}
            onPath={openFiles}
            stopped={stopped}
          />
        ) : route.view === "findings" ? (
          // Drawn anew for each text an address asks the tab for, as a file the banner names
          // leads to the findings holding its name: the filter opens holding it.
          <FindingsPage
            key={route.text ?? ""}
            state={state}
            text={route.text}
            stopped={stopped}
            onOpen={navigate}
          />
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
          <h1>{projectName(opened, project)}</h1>
        </div>
        {waiting !== null && <p className="quiet">{waiting}</p>}
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
              {projectName(opened, project)}
            </Button>
          )}
        </nav>
        {/* Once the open project's first analysis has landed, whose index the names are asked of:
            every page of the project, a component's among them, reaches a variable from here. */}
        {opened !== null && state !== null && (
          <GoTo revision={state.revision} stopped={stopped} onGo={navigate} />
        )}
      </header>
      {stopped && (
        <Banner tone="error">
          ddd gui has stopped. Start it again and open the address it prints.
        </Banner>
      )}
      {failure !== null && <Banner tone="error">{failure}</Banner>}
      {/* Every page of the open project, a component's among them, says what of it did not load,
          why its last analysis failed and which build records cannot be used (16:I9): drawn from
          the files that did load, a page alone said none of it. Outside the boundary, as the
          banners above are, so that a page that cannot be drawn leaves it standing. */}
      {banner !== null && <LoadBannerView banner={banner} onFollow={navigate} />}
      {/* Every screen reads whether the findings may be about to change from here, and says so
          where its findings are (spec 6). A page that throws while it is drawn is caught by the
          one boundary under the masthead and the banners (15:I5), which stay drawn. */}
      <UpdatingContext value={updating}>
        <ErrorBoundary
          route={route}
          fallback={(thrown) => (
            <UndrawnView
              failure={undrawnSentence(thrown)}
              stopped={stopped}
              onReload={() => window.location.reload()}
            />
          )}
        >
          <main>{page}</main>
        </ErrorBoundary>
      </UpdatingContext>
    </div>
  );
}
