import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { getSession } from "../api/client";
import { Banner } from "../components/Banner";
import { ComponentPage } from "../screens/ComponentPage";
import { ProjectPage } from "../screens/ProjectPage";
import { StartPage } from "../screens/StartPage";
import { useProjectState } from "./useProjectState";
import { useRoute } from "./useRoute";

export function App() {
  const queries = useQueryClient();
  const [route, navigate] = useRoute();
  const session = useQuery({ queryKey: ["session"], queryFn: () => getSession() });
  const opened = session.data?.project ?? null;
  const { state, stopped, failure } = useProjectState(opened !== null);

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
          navigate({ page: "project" });
        }}
      />
    );
  } else if (route.page === "project") {
    page = (
      <ProjectPage
        name={opened.name ?? opened.path}
        state={state}
        onComponent={(file) => navigate({ page: "component", file })}
      />
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
            <button type="button" className="link" onClick={() => navigate({ page: "project" })}>
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
