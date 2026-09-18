import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback } from "react";
import { getSession } from "../api/client";
import { hrefOf } from "../lib/route";
import { ComponentPage } from "../screens/ComponentPage";
import { GraphPage } from "../screens/GraphPage";
import { ProjectPage } from "../screens/ProjectPage";
import { StartPage } from "../screens/StartPage";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { LinkTabs } from "../ui/LinkTabs";
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
        <LinkTabs
          label="Project views"
          tabs={(["graph", "table"] as const).map((view) => ({
            href: hrefOf({ page: "project", view }),
            label: view === "graph" ? "Graph" : "Table",
            current: route.view === view,
            onFollow: () => navigate({ page: "project", view }),
          }))}
        />
        {route.view === "graph" ? (
          <GraphPage project={opened.path} state={state} onComponent={openComponent} />
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
