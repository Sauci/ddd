import { useQuery } from "@tanstack/react-query";
import {
  applyNodeChanges,
  Background,
  Controls,
  type NodeMouseHandler,
  type OnNodeDrag,
  type OnNodesChange,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import { type KeyboardEvent, useCallback, useMemo, useState } from "react";
import { getGraph } from "../api/client";
import type { GraphReply, State } from "../api/types";
import { Banner } from "../components/Banner";
import { FlowEdge } from "../components/FlowEdge";
import { ModuleNode } from "../components/ModuleNode";
import {
  brightOf,
  edgesOf,
  fadedNodes,
  firstMatch,
  type ModuleNodeType,
  nodesOf,
  shownEdges,
} from "../lib/canvas";
import { forgetPositions, rememberPosition, savedPositions } from "../state/positions";

// Outside the component on purpose: a fresh object here makes React Flow rebuild every node and
// every edge on each render, which it says so itself in the console.
const nodeTypes = { module: ModuleNode };
const edgeTypes = { flow: FlowEdge };

/** How long the viewport takes to fly to what `Fit` or a search asked for, in milliseconds. */
const FLIGHT = 300;

interface Props {
  project: string;
  state: State | null;
  onComponent: (file: string) => void;
}

/** The open project as a canvas: one node per module, one arrow per producing-consuming pair. */
export function GraphPage({ project, state, onComponent }: Props) {
  const graph = useQuery({
    // The project is in the key beside the revision: until the first state answer arrives the
    // revision is undefined, so two projects opened one after the other in the same session
    // would share that key and the second would open on the first one's modules.
    queryKey: ["graph", project, state?.revision],
    queryFn: () => getGraph(),
    // The canvas stays up while the next revision's graph is read: blanked back to "Drawing the
    // project…" on every edit, it lost the viewport and made the screen flash. Only the first
    // answer is waited for.
    placeholderData: (previous) => previous,
  });

  if (graph.data === undefined) {
    if (graph.isError) return <Banner tone="error">{graph.error.message}</Banner>;
    return <p className="quiet">Drawing the project…</p>;
  }
  return (
    <>
      {/* Spec 5.6: a server that stopped answering leaves the canvas as it was, and says so
          beside it - what is drawn is still the truth of the last revision that was read. */}
      {graph.isError && <Banner tone="error">{graph.error.message}</Banner>}
      {!graph.data.dictionary && (
        <Banner tone="warning">
          This project has no dictionary, so its modules are drawn without arrows.
        </Banner>
      )}
      <ReactFlowProvider>
        <Canvas graph={graph.data} project={project} onComponent={onComponent} />
      </ReactFlowProvider>
    </>
  );
}

/**
 * The canvas itself, mounted only once there is a graph to draw so that `fitView` has something
 * to fit. `onComponent` is baked into every node, so the caller keeps one identity for it.
 *
 * It lives under a `ReactFlowProvider` because the search box, `Tidy` and `Fit` sit outside the
 * `<ReactFlow>` element and still have to reach its viewport.
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
  const flow = useReactFlow();
  const [hovered, setHovered] = useState<string | null>(null);
  const [reached, setReached] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  /** Every module where it belongs right now: the reader's own position, or the layout's. */
  const place = useCallback(
    () => nodesOf(graph, savedPositions(project), onComponent),
    [graph, project, onComponent],
  );
  // React Flow moves a node only through the array it is handed back, so the nodes are state.
  const [nodes, setNodes] = useState<ModuleNodeType[]>(place);
  const [drawn, setDrawn] = useState(graph);
  if (drawn !== graph) {
    // A new revision lays the canvas out again (spec 5.1), keeping every module the reader
    // moved where they put it. Adjusted while rendering the new graph rather than in an effect,
    // so the previous revision's nodes are never painted against it.
    setDrawn(graph);
    setNodes(place());
  }
  const onNodesChange = useCallback<OnNodesChange<ModuleNodeType>>(
    (changes) => setNodes((current) => applyNodeChanges(changes, current)),
    [],
  );
  const onDragStop = useCallback<OnNodeDrag<ModuleNodeType>>(
    (_event, node) => rememberPosition(project, node.id, node.position.x, node.position.y),
    [project],
  );
  const onEnter = useCallback<NodeMouseHandler<ModuleNodeType>>(
    (_event, node) => setHovered(node.id),
    [],
  );
  const onLeave = useCallback<NodeMouseHandler<ModuleNodeType>>(() => setHovered(null), []);

  const onTidy = useCallback(() => {
    forgetPositions(project);
    setNodes(place());
  }, [project, place]);
  const onFit = useCallback(() => void flow.fitView({ duration: FLIGHT }), [flow]);
  const onSearchKey = useCallback(
    (event: KeyboardEvent<HTMLInputElement>) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const first = firstMatch(graph.modules, search);
      // Centred rather than zoomed onto: one module filling the canvas would answer "where is
      // it" by throwing away everything it is connected to.
      if (first !== null) {
        void flow.fitView({ nodes: [{ id: first }], duration: FLIGHT, maxZoom: 1 });
      }
    },
    [flow, graph, search],
  );

  const edges = useMemo(() => edgesOf(graph, setReached), [graph]);
  const bright = useMemo(
    () => brightOf(graph.modules, graph.flows, hovered, search),
    [graph, hovered, search],
  );
  const shownNodes = useMemo(() => fadedNodes(nodes, bright), [nodes, bright]);
  const shownArrows = useMemo(() => shownEdges(edges, bright, reached), [edges, bright, reached]);

  return (
    <>
      <div className="canvas-tools">
        <input
          // A textbox, not a search box: the journeys look for the role an <input type="text">
          // has, and the clear button a search field adds has nothing to clear here.
          type="text"
          aria-label="Search modules"
          placeholder="Search modules"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={onSearchKey}
        />
        <button type="button" onClick={onTidy}>
          Tidy
        </button>
        <button type="button" onClick={onFit}>
          Fit
        </button>
      </div>
      <section className="canvas" aria-label="Modules">
        <ReactFlow
          nodes={shownNodes}
          edges={shownArrows}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onNodesChange}
          onNodeDragStop={onDragStop}
          onNodeMouseEnter={onEnter}
          onNodeMouseLeave={onLeave}
          fitView
          // A reader reads this graph; they do not draw one, and they do not take a module out
          // of it either - the delete key would otherwise remove what it is pointing at until
          // the next revision put it back.
          nodesConnectable={false}
          deleteKeyCode={null}
          // The node is a box around a button: React Flow's own tab stop in front of it carries
          // no name and would put two stops in the way of every module.
          nodesFocusable={false}
        >
          <Background />
          {/* Tidy and Fit are this canvas's controls, named above it. React Flow's lock would
              write dragging and connecting back into its own store, past the props here, and
              its fit-view icon is Fit again without a name worth reading. */}
          <Controls showInteractive={false} showFitView={false} />
        </ReactFlow>
      </section>
    </>
  );
}
