import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, getFile, postEdit } from "../api/client";
import type { State } from "../api/types";
import { Banner } from "../components/Banner";
import { UnitEditor } from "../components/UnitEditor";
import { jsonText, setValue } from "../lib/edits";
import { keyedFindings } from "../lib/findings";
import type { ComponentFile } from "../lib/formats";
import { valueAt, within } from "../lib/pointer";
import { asList, asText } from "../lib/values";

interface Props {
  file: string;
  state: State | null;
  disabled: boolean;
}

/** One component: its declarations, a unit editor on each, and the findings located in it. */
export function ComponentPage({ file, state, disabled }: Props) {
  const queries = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const content = useQuery({
    queryKey: ["file", file, state?.revision],
    queryFn: () => getFile(file),
  });
  const edit = useMutation({
    mutationFn: ({ pointer, unit }: { pointer: string; unit: string }) => {
      if (content.data === undefined) throw new Error("the file has not been read yet");
      return postEdit(
        setValue(content.data.path, content.data.fingerprint, pointer, jsonText(unit)),
      );
    },
    onSuccess: () => setNotice(null),
    onError: (error) => {
      if (error instanceof ApiError && error.code === "stale") {
        setNotice(
          "This file changed on disk, so the change was not made. The page now shows the file as it is.",
        );
      } else {
        setNotice(`The change was refused: ${error.message}`);
      }
    },
    onSettled: () => queries.invalidateQueries({ queryKey: ["file", file] }),
  });

  if (content.isPending) return <p className="quiet">Reading the file…</p>;
  if (content.isError) return <Banner tone="error">{content.error.message}</Banner>;
  if (content.data.error !== null) return <Banner tone="error">{content.data.error}</Banner>;

  const data = content.data.data;
  // The file parsed but is only checked against the schema here: it need not match ComponentFile
  // (spec 6.10), so `component` may still be absent on disk even though the type makes it required.
  const name = (data as ComponentFile).component?.name ?? "Unnamed component";
  const findings = (state?.findings ?? []).filter((finding) => finding.file === file);
  return (
    <section>
      <h1>{name}</h1>
      {notice !== null && <Banner tone="warning">{notice}</Banner>}
      <table className="declarations">
        <thead>
          <tr>
            <th scope="col">Scope</th>
            <th scope="col">Name</th>
            <th scope="col">Kind</th>
            <th scope="col">Type</th>
            <th scope="col">Unit</th>
            <th scope="col">Findings</th>
          </tr>
        </thead>
        <tbody>
          {asList(valueAt(data, "component.interface")).map((_, index) => {
            const at = `component.interface[${index}]`;
            const declared =
              asText(valueAt(data, `${at}.definition.name`)) ?? `declaration ${index + 1}`;
            const own = findings.filter((finding) => within(finding.pointer, at));
            return (
              <tr
                key={at}
                className={
                  own.some((finding) => finding.severity === "error") ? "has-error" : undefined
                }
              >
                <td>{asText(valueAt(data, `${at}.scope`))}</td>
                <td>{declared}</td>
                <td>{asText(valueAt(data, `${at}.definition.kind`))}</td>
                <td>
                  {asText(valueAt(data, `${at}.definition.datatype`)) ??
                    asText(valueAt(data, `${at}.definition.typename`))}
                </td>
                <td>
                  <UnitEditor
                    name={declared}
                    unit={asText(valueAt(data, `${at}.definition.unit`)) ?? ""}
                    disabled={disabled || edit.isPending}
                    onConfirm={(unit) => edit.mutate({ pointer: `${at}.definition.unit`, unit })}
                  />
                </td>
                <td>
                  {keyedFindings(own).map(([finding, key]) => (
                    <span key={key} className={`badge ${finding.severity}`}>
                      {finding.check}
                    </span>
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h2>Findings in this component</h2>
      {findings.length === 0 ? (
        <p className="quiet">None.</p>
      ) : (
        <ul className="findings">
          {keyedFindings(findings).map(([finding, key]) => (
            <li key={key} className={finding.severity}>
              <span className="check">{finding.check}</span>{" "}
              <span className="message">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
