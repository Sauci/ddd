import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback } from "react";
import { getSession } from "../api/client";
import { hrefOf } from "../lib/route";
import { ComponentPage } from "../screens/ComponentPage";
import { FindingsPage } from "../screens/FindingsPage";
import { GraphPage } from "../screens/GraphPage";
import { ProjectPage } from "../screens/ProjectPage";
import { StartPage } from "../screens/StartPage";
import { UndoStrip } from "../screens/UndoStrip";
import { UnitsPage } from "../screens/UnitsPage";
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
  ["findings", "Findings"],
] as const;

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
            href: hrefOf({ page: "project", view }),
            label,
            current: route.view === view,
            onFollow: () => navigate({ page: "project", view }),
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
          />
        ) : route.view === "units" ? (
          <UnitsPage state={state} unit={route.unit} stopped={stopped} onUnit={openUnit} />
        ) : route.view === "findings" ? (
          <FindingsPage state={state} stopped={stopped} onOpen={navigate} />
        ) : (
          <ProjectPage state={state} onComponent={openComponent} />
        )}
      </section>
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
