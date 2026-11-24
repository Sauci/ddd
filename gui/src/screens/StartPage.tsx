import { useMutation, useQuery } from "@tanstack/react-query";
import { getProjects, openProject } from "../api/client";
import {
  ALREADY_OPEN,
  isOpen,
  listHeld,
  noProjectSentence,
  UNREAD_HEADING,
  unreadLine,
  unreadShown,
} from "../lib/start";
import { Banner } from "../ui/Banner";
import { PageHeading } from "../ui/PageHeading";

/** The projects found where `ddd gui` was started, to open one of them - or, for the project
 * `open` names, the one open, to go back to it as it stands (`onGo`), never opened again. */
export function StartPage({
  open,
  onOpened,
  onGo,
}: {
  open: string | null;
  onOpened: () => void;
  onGo: () => void;
}) {
  const found = useQuery({ queryKey: ["projects"], queryFn: () => getProjects() });
  const opening = useMutation({
    mutationFn: (path: string) => openProject(path),
    onSuccess: onOpened,
  });

  if (found.isPending) return <p className="quiet">Looking for projects…</p>;
  if (found.isError) return <Banner tone="error">{found.error.message}</Banner>;
  return (
    <section>
      <PageHeading>Open a project</PageHeading>
      <p className="quiet">Found under {found.data.root}</p>
      {found.data.projects.length === 0 ? (
        <p>{noProjectSentence(found.data.unreadable.length)}</p>
      ) : (
        <ul className="projects">
          {found.data.projects.map((project) => {
            const here = isOpen(project.path, open);
            return (
              <li key={project.path}>
                <button
                  type="button"
                  disabled={listHeld(opening.status)}
                  aria-current={here ? "true" : undefined}
                  onClick={() => (here ? onGo() : opening.mutate(project.path))}
                >
                  <span className="name">{project.name ?? "Unnamed project"}</span>
                  <span className="path">{project.path}</span>
                  {project.images.length > 0 && (
                    <span className="quiet">built as {project.images.join(", ")}</span>
                  )}
                  {here && <span className="open">{ALREADY_OPEN}</span>}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {unreadShown(found.data.unreadable) && (
        <>
          <h2>{UNREAD_HEADING}</h2>
          <ul className="unreadable">
            {found.data.unreadable.map((entry) => (
              <li key={entry.path}>{unreadLine(entry)}</li>
            ))}
          </ul>
        </>
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
      {opening.isError && <Banner tone="error">{opening.error.message}</Banner>}
    </section>
  );
}
