import { useQuery } from "@tanstack/react-query";
import { Background, Controls, type Edge, MarkerType, type Node, ReactFlow } from "@xyflow/react";
import { useMemo } from "react";
import { getGraph } from "../api/client";
import type { GraphReply, State } from "../api/types";
import { Banner } from "../components/Banner";
import { type FlowData, FlowEdge, STROKE, stateOf } from "../components/FlowEdge";
import { type ModuleData, ModuleNode } from "../components/ModuleNode";
import { laidOut } from "../lib/layout";
import { savedPositions } from "../state/positions";

type ModuleNodeType = Node<ModuleData, "module">;
type FlowEdgeType = Edge<FlowData, "flow">;

// Outside the component on purpose: a fresh object here makes React Flow rebuild every node and
// every edge on each render, which it says so itself in the console.
const nodeTypes = { module: ModuleNode };
const edgeTypes = { flow: FlowEdge };

interface Props {
  project: string;
  state: State | null;
  onComponent: (file: string) => void;
}

/** The open project as a canvas: one node per module, one arrow per producing-consuming pair. */
export function GraphPage({ project, state, onComponent }: Props) {
  const graph = useQuery({
    queryKey: ["graph", state?.revision],
    queryFn: () => getGraph(),
    // The canvas stays up while the next revision's graph is read: blanked back to "Drawing the
    // project…" on every edit, it lost the viewport and made the screen flash. Only the first
    // answer is waited for.
    placeholderData: (previous) => previous,
  });

  if (graph.isPending) return <p className="quiet">Drawing the project…</p>;
  if (graph.isError) return <Banner tone="error">{graph.error.message}</Banner>;

  // The endpoint answers no flows both when the dictionary did not resolve (spec 4.5) and when
  // the modules genuinely share nothing, and nothing in its answer tells the two apart. Several
  // modules with not one flow between them is, in practice, a dictionary that did not resolve.
  const noDictionary = graph.data.modules.length > 1 && graph.data.flows.length === 0;
  return (
    <>
      {noDictionary && (
        <Banner tone="warning">
          This project has no dictionary, so its modules are drawn without arrows.
        </Banner>
      )}
      <Canvas graph={graph.data} project={project} onComponent={onComponent} />
    </>
  );
}

/**
 * The canvas itself, mounted only once there is a graph to draw so that `fitView` has something
 * to fit. `onComponent` is baked into every node, so the caller keeps one identity for it.
 */
function Canvas({
  graph,
  project,
  onComponent,
}: {
  graph: GraphReply;
  project: string;
  onComponent: (file: string) => void;
}) {
  const nodes = useMemo(() => nodesOf(graph, project, onComponent), [graph, project, onComponent]);
  const edges = useMemo(() => edgesOf(graph), [graph]);
  return (
    <section className="canvas" aria-label="Modules">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        // A reader reads this graph; they do not draw one. Dragging arrives with the arrangement
        // Task 5 remembers, and React Flow moves a node only for an `onNodesChange` that saves it.
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </section>
  );
}

/** Every module, where the layout puts it, with what its node has to draw. */
function nodesOf(
  graph: GraphReply,
  project: string,
  onOpen: (path: string) => void,
): ModuleNodeType[] {
  const placed = new Map(
    laidOut(graph.modules, graph.flows, savedPositions(project)).map((at) => [at.path, at]),
  );
  return graph.modules.map((module) => {
    // laidOut places every module it is given; the fallback is only here to satisfy the type.
    const at = placed.get(module.path) ?? { x: 0, y: 0 };
    return {
      id: module.path,
      type: "module",
      position: { x: at.x, y: at.y },
      data: {
        name: module.name,
        loaded: module.loaded,
        errors: module.findings.error,
        warnings: module.findings.warning,
        onOpen,
        faded: false,
      },
    };
  });
}

/** Every flow as an arrow, carrying the two modules' names rather than their paths. */
function edgesOf(graph: GraphReply): FlowEdgeType[] {
  const names = new Map(graph.modules.map((module) => [module.path, module.name]));
  return graph.flows.map((flow) => {
    const stroke = STROKE[stateOf(flow.severity)];
    return {
      id: `${flow.from} -> ${flow.to}`,
      source: flow.from,
      target: flow.to,
      type: "flow",
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 18, height: 18 },
      // React Flow would otherwise announce the arrow by the two file paths, which this screen
      // never shows; the label carries the whole sentence a reader needs.
      domAttributes: { "aria-hidden": true },
      data: {
        source: names.get(flow.from) ?? flow.from,
        target: names.get(flow.to) ?? flow.to,
        objects: flow.objects,
        severity: flow.severity,
        disagreements: flow.disagreements,
        faded: false,
      },
    };
  });
}
