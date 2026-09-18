// The JSON the server answers with (src/ddd/gui/api.py), shape for shape.

export interface SessionInfo {
  version: string;
  preview: boolean;
  root: string;
  project: { path: string; name: string | null } | null;
  builds: { image: string; strict: boolean; severity: string[] }[];
}

export interface FoundProject {
  path: string;
  name: string | null;
  images: string[];
}

export interface Found {
  root: string;
  projects: FoundProject[];
  refused: { record: string; reason: string }[];
}

export type Severity = "error" | "warning" | "info";

export interface Note {
  message: string;
  file: string | null;
  pointer: string;
}

export interface Finding {
  file: string;
  check: string;
  severity: Severity;
  message: string;
  pointer: string;
  notes: Note[];
}

export interface SourceFile {
  path: string;
  kind: string;
  name: string | null;
  loaded: boolean;
  fingerprint: string;
  findings: Record<Severity, number>;
}

export interface State {
  revision: number;
  project: string;
  files: SourceFile[];
  findings: Finding[];
}

export interface FileContent {
  path: string;
  fingerprint: string;
  data: unknown;
  error: string | null;
}

export type Operation =
  | { op: "set"; pointer: string; raw: string }
  | { op: "remove"; pointer: string }
  | { op: "insert"; pointer: string; raw: string }
  | { op: "move"; pointer: string; to: number };

export interface Change {
  file: string;
  fingerprint: string;
  operations: Operation[];
}

export interface Changes {
  changes: Change[];
}

export interface EditReply {
  revision: number;
  files: { path: string; fingerprint: string }[];
}
