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
import { FlowEdge } from "../components/FlowEdge";
import { ModuleNode } from "../components/ModuleNode";
import {
  brightOf,
  edgesOf,
  fadedNodes,
  firstMatch,
  flowTitle,
  type ModuleNodeType,
  nodesOf,
  objectsInDisagreement,
  shownEdges,
} from "../lib/canvas";
import { forgetPositions, rememberPosition, savedPositions } from "../state/positions";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Panel } from "../ui/Panel";
import { VariablePanel } from "./VariablePanel";

// Outside the component on purpose: a fresh object here makes React Flow rebuild every node and
// every edge on each render, which it says so itself in the console.
const nodeTypes = { module: ModuleNode };
const edgeTypes = { flow: FlowEdge };

/** How long the viewport takes to fly to what `Fit` or a search asked for, in milliseconds. */
const FLIGHT = 300;

interface Props {
  project: string;
  state: State | null;
  variable: string | undefined;
  stopped: boolean;
  onComponent: (file: string) => void;
  onVariable: (variable: string | undefined) => void;
}

/** The open project as a canvas: one node per module, one arrow per producing-consuming pair. */
export function GraphPage({ project, state, variable, stopped, onComponent, onVariable }: Props) {
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
        <Canvas
          graph={graph.data}
          project={project}
          variable={variable}
          revision={state?.revision}
          stopped={stopped}
          onComponent={onComponent}
          onVariable={onVariable}
        />
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
  variable,
  revision,
  stopped,
  onComponent,
  onVariable,
}: {
  graph: GraphReply;
  project: string;
  variable: string | undefined;
  revision: number | undefined;
  stopped: boolean;
  onComponent: (file: string) => void;
  onVariable: (variable: string | undefined) => void;
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

  // An arrow in disagreement about several variables asks which one; one about a single
  // variable opens it straight away, and an arrow whose ends agree opens nothing.
  const [chooser, setChooser] = useState<{ title: string; objects: string[] } | null>(null);
  // The variable whose panel closed because no file declares it any longer (spec 5.5), named
  // above the canvas until another variable is opened or the reader leaves the canvas.
  const [undeclared, setUndeclared] = useState<string | null>(null);
  const onOpen = useCallback(
    (id: string) => {
      const objects = objectsInDisagreement(graph, id);
      if (objects.length === 1) {
        setChooser(null);
        setUndeclared(null);
        onVariable(objects[0]);
      } else if (objects.length > 1) {
        onVariable(undefined);
        setChooser({ title: flowTitle(graph, id), objects });
      }
    },
    [graph, onVariable],
  );
  const edges = useMemo(() => edgesOf(graph, setReached, onOpen), [graph, onOpen]);
  const bright = useMemo(
    () => brightOf(graph.modules, graph.flows, hovered, search),
    [graph, hovered, search],
  );
  const shownNodes = useMemo(() => fadedNodes(nodes, bright), [nodes, bright]);
  const shownArrows = useMemo(() => shownEdges(edges, bright, reached), [edges, bright, reached]);

  return (
    <div className={variable !== undefined || chooser !== null ? "with-panel" : undefined}>
      <div>
        {undeclared !== null && (
          <Banner tone="warning">{undeclared} is no longer declared in the open project.</Banner>
        )}
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
          <Button onPress={onTidy}>Tidy</Button>
          <Button onPress={onFit}>Fit</Button>
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
      </div>
      {variable !== undefined ? (
        <VariablePanel
          key={variable}
          name={variable}
          revision={revision}
          stopped={stopped}
          focusPicker={null}
          onClose={() => onVariable(undefined)}
          onUndeclared={() => {
            setUndeclared(variable);
            onVariable(undefined);
          }}
        />
      ) : (
        chooser !== null && (
          <Panel title={chooser.title} onClose={() => setChooser(null)}>
            <ul className="panel-choices">
              {chooser.objects.map((object) => (
                <li key={object}>
                  <Button
                    variant="link"
                    onPress={() => {
                      setChooser(null);
                      setUndeclared(null);
                      onVariable(object);
                    }}
                  >
                    {object}
                  </Button>
                </li>
              ))}
            </ul>
          </Panel>
        )
      )}
    </div>
  );
}
