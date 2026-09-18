import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback } from "react";
import { getSession } from "../api/client";
import { hrefOf, type ProjectView } from "../lib/route";
import { ComponentPage } from "../screens/ComponentPage";
import { GraphPage } from "../screens/GraphPage";
import { ProjectPage } from "../screens/ProjectPage";
import { StartPage } from "../screens/StartPage";
import { Banner } from "../ui/Banner";
import { useProjectState } from "./useProjectState";
import { useRoute } from "./useRoute";

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
        <h1>{opened.name ?? opened.path}</h1>
        <nav className="tabs" aria-label="Project views">
          <Tab view="graph" open={route.view} navigate={navigate}>
            Graph
          </Tab>
          <Tab view="table" open={route.view} navigate={navigate}>
            Table
          </Tab>
        </nav>
        {route.view === "graph" ? (
          <GraphPage project={opened.path} state={state} onComponent={openComponent} />
        ) : (
          <ProjectPage state={state} onComponent={openComponent} />
        )}
      </section>
    );
  } else {
    page = <ComponentPage file={route.file} state={state} disabled={stopped} />;
  }

  return (
    <div className="app">
      <header className="masthead">
        <span className="brand">ddd gui</span>
        <span className="preview">preview</span>
        <nav>
          <button type="button" className="link" onClick={() => navigate({ page: "start" })}>
            Projects
          </button>
          {opened !== null && (
            <button
              type="button"
              className="link"
              onClick={() => navigate({ page: "project", view: "graph" })}
            >
              {opened.name ?? opened.path}
            </button>
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

/** One of the project screen's tabs: a real address, so a reload and the back button keep it. */
function Tab({
  view,
  open,
  navigate,
  children,
}: {
  view: ProjectView;
  open: ProjectView;
  navigate: (route: { page: "project"; view: ProjectView }) => void;
  children: ReactNode;
}) {
  return (
    <a
      href={hrefOf({ page: "project", view })}
      aria-current={view === open ? "page" : undefined}
      onClick={(event) => {
        // A modified or secondary click is the reader asking the browser for a new tab or a new
        // window: it is a real address, so let the browser have it rather than swallowing it.
        const modified = event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
        if (modified || event.button !== 0) return;
        event.preventDefault();
        navigate({ page: "project", view });
      }}
    >
      {children}
    </a>
  );
}
