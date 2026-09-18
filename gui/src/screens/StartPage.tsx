import { useMutation, useQuery } from "@tanstack/react-query";
import { getProjects, openProject } from "../api/client";
import { Banner } from "../components/Banner";

/** The projects found where `ddd gui` was started, to open one of them. */
export function StartPage({ onOpened }: { onOpened: () => void }) {
  const found = useQuery({ queryKey: ["projects"], queryFn: () => getProjects() });
  const open = useMutation({
    mutationFn: (path: string) => openProject(path),
    onSuccess: onOpened,
  });

  if (found.isPending) return <p className="quiet">Looking for projects…</p>;
  if (found.isError) return <Banner tone="error">{found.error.message}</Banner>;
  return (
    <section>
      <h1>Open a project</h1>
      <p className="quiet">Found under {found.data.root}</p>
      {found.data.projects.length === 0 ? (
        <p>No project description was found here. Start ddd gui with the path of one.</p>
      ) : (
        <ul className="projects">
          {found.data.projects.map((project) => (
            <li key={project.path}>
              <button
                type="button"
                disabled={open.isPending}
                onClick={() => open.mutate(project.path)}
              >
                <span className="name">{project.name ?? "Unnamed project"}</span>
                <span className="path">{project.path}</span>
                {project.images.length > 0 && (
                  <span className="quiet">built as {project.images.join(", ")}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
      {found.data.refused.length > 0 && (
        <>
          <h2>Build records not used</h2>
          <ul className="refused">
            {found.data.refused.map((entry) => (
              <li key={entry.record}>
                <span className="path">{entry.record}</span>: {entry.reason}
              </li>
            ))}
          </ul>
        </>
      )}
      {open.isError && <Banner tone="error">{open.error.message}</Banner>}
    </section>
  );
}
