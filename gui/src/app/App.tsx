import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { getSession } from "../api/client";
import { signedOut } from "../api/token";
import { LoadBannerView } from "../components/LoadBannerView";
import { SignedOutView } from "../components/SignedOutView";
import { UndrawnView } from "../components/UndrawnView";
import { PROJECT_VIEWS, pageTitle, VIEW_NAMES, wayBack } from "../lib/announcing";
import type { CompareHeld } from "../lib/compare";
import type { FindingsPlace } from "../lib/findingsWindow";
import { headingAsked, pageOf, type Shown } from "../lib/focus";
import {
  findingsLeadsTo,
  hrefOf,
  type ProjectView,
  type Route,
  type ShownLast,
  shownLastAfter,
  tabHref,
  takesWindow,
} from "../lib/route";
import { projectName, sessionAskedFor } from "../lib/session";
import type { SharedKind } from "../lib/shared";
import { undrawnSentence } from "../lib/undrawn";
import { loadBanner, unloadedNames } from "../lib/unloaded";
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
import { PageHeading } from "../ui/PageHeading";
import { UpdatingStatus } from "../ui/UpdatingNote";
import { ErrorBoundary } from "./ErrorBoundary";
import { analysisLanded, askHeading, watchFocus } from "./focus";
import { UpdatingContext } from "./updating";
import { useProjectState } from "./useProjectState";
import { useRoute } from "./useRoute";
import { useWritten } from "./useWritten";

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
  const [route, navigate, arrived, followings] = useRoute();
  // Which control a press of the pointer is on, for the panel it opens to give the focus back to;
  // whether the reader pressed a key or the pointer, turned the wheel or touched the page since a
  // change of page asked for its heading; where the focus goes that the page takes away with a
  // control, never to the page's body; and whether the focus came by Tab, which a grid's field asks
  // as it takes it.
  useEffect(() => watchFocus(), []);
  // A change of page - a link or a row followed, Back or Forward - puts the focus on the new page's
  // heading, as a page loaded starts at its top: the control that held it is gone with the page
  // before, or names it no longer (16:I13). What a page selects in itself is no change of page;
  // one whose address names such a selection puts it on the heading of the panel the page draws for
  // it, the panel being what the reader asked for, scrolled into view (ruling B11-41) - and so does
  // a following to such an address on the page already shown, the masthead's go-to used on the
  // component's page it opens on. A page loaded anew at one scrolls its panel into view and moves
  // no focus (ruling B11-44): `headingAsked` decides, from no route shown before.
  const shown = useRef<Shown | null>(null);
  useEffect(() => {
    const asked = headingAsked(shown.current, { route, followings });
    if (asked !== null) askHeading(asked);
    shown.current = { route, followings };
  }, [route, followings]);
  const out = useSyncExternalStore(signedOut.subscribe, signedOut.current);
  const session = useQuery({ queryKey: ["session"], queryFn: () => getSession() });
  const opened = session.data?.project ?? null;
  const { state, project, failed, refused, updating, stopped, failure } = useProjectState(
    opened !== null,
  );
  // The pages of the project last shown (16:M16): the tab, which a component's page leads back to,
  // and the Findings tab's own address, its filter's text, which that tab's link leads back to.
  // Noted as each is shown, of the project the state is of (`shownLastAfter`).
  const [shownLast, setShownLast] = useState<ShownLast | null>(null);
  const shownNow = shownLastAfter(shownLast, project, route);
  if (shownNow !== shownLast) setShownLast(shownNow);
  // The Findings tab's place (16:M16) - the listing asked, its box's scroll and the finding whose
  // panel is open - held here, above the tab, while another page is shown, for the tab drawn anew
  // to open at: in the page's memory, written as the tab moves without drawing the page again.
  const findingsPlace = useRef<FindingsPlace | null>(null);
  const heldPlace = useCallback(() => findingsPlace.current, []);
  const holdPlace = useCallback((place: FindingsPlace) => {
    findingsPlace.current = place;
  }, []);
  // What a page loaded anew waits to show waits the short time from the landing of the project's
  // first analysis (ruling B11-47). Before it, a page draws no more than the project's heading -
  // with its tabs, on a tab of the project - and the line saying the analysis is on its way, so that
  // a slow analysis takes none of that time. What a page reads of its own once it has landed is
  // counted in: a tab's answer, the Graph's layout, a component's file, the page drawing the line
  // that says so meanwhile - a component's page, "Reading the file…" alone.
  const analysed = state !== null;
  useEffect(() => {
    if (analysed) analysisLanded();
  }, [analysed]);
  // Asked again for each project the state followed comes to be of while the session names
  // another: another page of the same server opened it (`sessionAskedFor`, lib/session.ts). Keyed
  // by that project, so that a state moving on while an ask is out asks once more, cancelling the
  // ask before it, whose answer may name the project before.
  const askedFor = sessionAskedFor(opened, project);
  useEffect(() => {
    if (askedFor !== null) void queries.invalidateQueries({ queryKey: ["session"] });
  }, [askedFor, queries]);
  // Each page titled by its name and the project's (16:I13), as what is drawn below names them:
  // the start page where no project is open, nothing of a page before the session answers.
  const title = pageTitle({
    drawn: !out && session.isSuccess,
    route,
    project: opened === null ? null : projectName(opened, project),
    files: state?.files ?? [],
  });
  useEffect(() => {
    document.title = title;
  }, [title]);
  // What the project screen's heading says the page last wrote, on the tab it was written on.
  const written = useWritten(pageOf(route));
  // What the Compare tab holds - its field, and the comparison last asked for, whose answer is its
  // verdict - kept here, above the tab, while another tab is shown (16:M2): in the page's memory,
  // never in the address, and of the project it was asked of (`heldFor`).
  const [compareHeld, setCompareHeld] = useState<CompareHeld | null>(null);
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
  // The Findings tab's filter replaces the address once typing pauses, as a selection does (16:I9):
  // a reload opens the tab on it, and a link to a file's findings, pressed after other text was
  // typed, leads to another address than the one the page is at.
  const filterFindings = useCallback(
    (text: string) =>
      navigate(
        text === ""
          ? { page: "project", view: "findings" }
          : { page: "project", view: "findings", text },
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
  // Once the server has stopped, it promises nothing ddd gui would do.
  const banner =
    session.isSuccess && opened !== null && route.page !== "start"
      ? loadBanner(project, state, failed, refused, stopped)
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
          <PageHeading>{projectName(opened, project)}</PageHeading>
          <UndoStrip state={state} stopped={stopped} />
          {/* Last in the row, so that none of the controls before it ever moves. */}
          <UpdatingStatus updating={updating} written={written} />
        </div>
        <LinkTabs
          label="Project views"
          tabs={PROJECT_VIEWS.map((view) => {
            // The Findings tab leads back to its own address last shown, its filter's text, and
            // opens at its place (16:M16); every other tab to itself with nothing selected.
            const to = view === "findings" ? findingsLeadsTo(shownNow, project) : BARE_ROUTES[view];
            return {
              href: hrefOf(to) ?? tabHref(view),
              label: VIEW_NAMES[view],
              current: route.view === view,
              onFollow: () => navigate(to),
            };
          })}
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
            onOpen={navigate}
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
          // Drawn anew at each following - a link pressed, the banner's to a file's findings and
          // the tab's own among them, Back or Forward - its filter opening on the text the address
          // asks for, whatever was typed since; and left as it is while the address follows what
          // the filter asks, which is no following.
          <FindingsPage
            key={followings}
            state={state}
            text={route.text}
            onText={filterFindings}
            place={heldPlace}
            onPlace={holdPlace}
            stopped={stopped}
            onOpen={navigate}
          />
        ) : route.view === "compare" ? (
          <ComparePage
            state={state}
            stopped={stopped}
            held={compareHeld}
            onHeld={setCompareHeld}
            onOpen={navigate}
          />
        ) : (
          <ProjectPage state={state} onComponent={openComponent} onOpen={navigate} />
        )}
      </section>
    );
  } else if (state === null) {
    // A component's page, or its values, before the project's first analysis: named by the
    // project, the one name known yet, and nothing of the file asked for until there is one.
    page = (
      <section>
        <div className="heading">
          <PageHeading>{projectName(opened, project)}</PageHeading>
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
        wayBack={wayBack(shownNow, project)}
        onFollow={navigate}
      />
    );
  }

  return (
    <div className={takesWindow(route) ? "app wide" : "app"}>
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
          <GoTo
            revision={state.revision}
            unread={unloadedNames(state.files)}
            stopped={stopped}
            onGo={navigate}
          />
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
