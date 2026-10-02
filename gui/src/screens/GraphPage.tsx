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
import { type KeyboardEvent, useCallback, useMemo, useRef, useState } from "react";
import { getGraph } from "../api/client";
import type { GraphReply, State } from "../api/types";
import { useLayout } from "../app/useLayout";
import { FlowEdge } from "../components/FlowEdge";
import { ModuleNode } from "../components/ModuleNode";
import {
  brightOf,
  edgesOf,
  fadedNodes,
  firstMatch,
  flowTitle,
  MIN_ZOOM,
  type ModuleNodeType,
  nodesOf,
  objectsInDisagreement,
  openingViewport,
  shownEdges,
  withSavedPositions,
} from "../lib/canvas";
import { layoutScreen } from "../lib/layoutAnswers";
import { visibleOnly } from "../lib/shape";
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
  /** Following a fixed key of the open variable's panel to the type that fixes it. */
  onOpenType: (name: string) => void;
  /** Following a `dimensions` entry of the open variable's panel to the constant it names. */
  onOpenConstant: (name: string) => void;
}

/** The open project as a canvas: one node per module, one arrow per producing-consuming pair. */
export function GraphPage({
  project,
  state,
  variable,
  stopped,
  onComponent,
  onVariable,
  onOpenType,
  onOpenConstant,
}: Props) {
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
          onOpenType={onOpenType}
          onOpenConstant={onOpenConstant}
        />
      </ReactFlowProvider>
    </>
  );
}

/**
 * The canvas itself, mounted only once there is a graph to draw, so that `fitView` has something
 * to fit once laid out. `onComponent` is baked into every node, so the caller keeps one identity
 * for it.
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
  onOpenType,
  onOpenConstant,
}: {
  graph: GraphReply;
  project: string;
  variable: string | undefined;
  revision: number | undefined;
  stopped: boolean;
  onComponent: (file: string) => void;
  onVariable: (variable: string | undefined) => void;
  onOpenType: (name: string) => void;
  onOpenConstant: (name: string) => void;
}) {
  // Called unconditionally, like every hook below, never behind the `layoutScreen` branch at the
  // foot of this function (the rules of hooks): `graph` is this call's own real modules and
  // flows, never a placeholder, since `GraphPage` above mounts `Canvas` only once it has a graph
  // to draw - so the first answer this hook ever receives is already the one this project's
  // reader is waiting for, not a throwaway layout of nothing that would make `placed` stop being
  // `null` before a real one has arrived.
  const layout = useLayout(graph.modules, graph.flows);
  const screen = layoutScreen(layout);
  const flow = useReactFlow();
  const [hovered, setHovered] = useState<string | null>(null);
  const [reached, setReached] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  /** The placement actually drawn: the layout's own, with the reader's saved positions laid over
   * it (`withSavedPositions`) - what both the opening view and `Fit` decide against, so neither
   * ever answers from a module's un-moved position once the reader has dragged it (review fix
   * round 2, item 1: the re-review found the first attempt deciding from the bare layout
   * instead). `null` only before the first layout for this shape has arrived. */
  const drawnPlacement = useCallback(
    () =>
      layout.placed === null ? null : withSavedPositions(layout.placed, savedPositions(project)),
    [layout.placed, project],
  );
  /** Every module where it belongs right now, with every module's data as fresh as `graph` -
   * `useLayout` keeps `placed` as it was for a revision whose shape did not change, this is what
   * still takes that revision's new counts and `loaded` to the nodes it draws. Nothing to place
   * before the first layout has arrived. */
  const place = useCallback(() => {
    const placement = drawnPlacement();
    return placement === null ? [] : nodesOf(placement, graph.modules, onComponent);
  }, [drawnPlacement, graph, onComponent]);
  // React Flow moves a node only through the array it is handed back, so the nodes are state.
  const [nodes, setNodes] = useState<ModuleNodeType[]>(place);
  const [drawn, setDrawn] = useState({ graph, placed: layout.placed });
  if (drawn.graph !== graph || drawn.placed !== layout.placed) {
    // A new revision, or a freshly made layout for one, draws the canvas again (spec 5.1),
    // keeping every module the reader moved where they put it. Adjusted while rendering rather
    // than in an effect, so the previous revision's nodes are never painted against this one.
    // Plainly `place()`, with no carrying-over of a previous node's own measured size: every
    // node `nodesOf` builds already carries its own (`measured`/`handles`, review fix round 2,
    // Finding 7), the same known box regardless of which node it replaces.
    setDrawn({ graph, placed: layout.placed });
    setNodes(place());
  }
  /**
   * The canvas element's own box, measured the moment the element exists at all - a ref callback
   * runs synchronously during React's commit, before paint, the same timing class as
   * `useLayoutEffect` - rather than in an effect that would run a tick later. `<ReactFlow>`
   * itself mounts only once `containerSize` is known (below): this "two-pass mount" is what lets
   * `openingViewport` (review fix round 2, item 1, replacing round 1's Ruling T10-2) be given to
   * it as `defaultViewport`, applied once, synchronously, on that first mount - rather than
   * raced against React Flow's own `fitView`, which does not finish synchronously within React's
   * commit at all: it waits for every node to report its measured size
   * (`@xyflow/system`'s `useOnInitHandler` only calls `onInit` once its own `viewportInitialized`
   * turns true, itself behind a `setTimeout`). A correction applied through `onInit`, tried in
   * round 1, is still only ever a race for which of the two runs last - confirmed by hand that
   * round's own fix usually won it, and the re-review's own by-hand check that it just as often
   * did not. `defaultViewport` has no such race to lose: nothing runs after it to overwrite it,
   * because `fitView` is not asked for at all (`fitView={false}`, below).
   */
  const containerRef = useRef<HTMLElement | null>(null);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number } | null>(
    null,
  );
  const canvasRef = useCallback((node: HTMLElement | null) => {
    containerRef.current = node;
    if (node === null) return;
    const box = node.getBoundingClientRect();
    setContainerSize({ width: box.width, height: box.height });
  }, []);
  // `null` until `containerSize` is - `<ReactFlow>` itself does not mount before then either
  // (below), so this is never handed to it as a stale or default viewport for the wrong size -
  // and, once computed, kept rather than redone: `defaultViewport` is only ever read on
  // `<ReactFlow>`'s own first mount, so recomputing this on a later render this component makes
  // for its own reasons (a hover, a keystroke in the search box) would be an O(placed) pass -
  // thousands of modules, at this task's own largest sizes - spent on a value nothing reads
  // again. Deliberately not keyed on `drawnPlacement` either: only `containerSize` becoming
  // known should ever (re)compute this one-time value, the same reason `defaultViewport` is
  // never updated once mounted, below.
  // biome-ignore lint/correctness/useExhaustiveDependencies: see above.
  const opening = useMemo(
    () =>
      containerSize === null
        ? null
        : openingViewport(drawnPlacement() ?? [], containerSize, MIN_ZOOM),
    [containerSize],
  );
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
  /**
   * The same rule the opening view decides by (`openingViewport`, above), applied again: `Fit`
   * re-measures the canvas element fresh, rather than trusting `containerSize` (set once, at
   * mount, and never again), so a window resized since opening is still answered correctly -
   * React Flow's own `fitView` always re-measured this way too, and this keeps that part of its
   * behaviour even though it is no longer what calls it.
   */
  const onFit = useCallback(() => {
    const box = containerRef.current?.getBoundingClientRect();
    const placement = drawnPlacement();
    if (box === undefined || placement === null) return;
    const view = openingViewport(placement, { width: box.width, height: box.height }, MIN_ZOOM);
    if (view !== null) void flow.setViewport(view, { duration: FLIGHT });
  }, [flow, drawnPlacement]);
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

  // `layoutScreen` (`gui/src/lib/layoutAnswers.ts`) is the whole decision (review fix round 1,
  // Minor 6): this reads its tag and draws accordingly, deciding nothing about when either
  // applies itself.
  if (screen.kind === "waiting") return <p className="quiet">Laying the project out…</p>;
  if (screen.kind === "failed") return <Banner tone="error">{screen.message}</Banner>;
  return (
    <div className={variable !== undefined || chooser !== null ? "with-panel" : undefined}>
      <div>
        {screen.errorMessage !== null && <Banner tone="error">{screen.errorMessage}</Banner>}
        {screen.note !== null && <p className="quiet">{screen.note}</p>}
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
        <section className="canvas" aria-label="Modules" ref={canvasRef}>
          {containerSize !== null && (
            <ReactFlow
              nodes={shownNodes}
              edges={shownArrows}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodesChange={onNodesChange}
              onNodeDragStop={onDragStop}
              onNodeMouseEnter={onEnter}
              onNodeMouseLeave={onLeave}
              // Never asked for (review fix round 2, item 1): `defaultViewport`, below, is what
              // opens the canvas on the right view now, applied once, synchronously, on this
              // mount, with nothing running after it - fitView's own correction - to overwrite
              // it.
              fitView={false}
              // Only present when there is one: exactOptionalPropertyTypes makes
              // `defaultViewport: undefined` a type error of its own, the same reason `edgesOf`
              // (`gui/src/lib/canvas.ts`) spreads `ariaRole` in conditionally rather than falling
              // back past the key.
              {...(opening !== null ? { defaultViewport: opening } : {})}
              // Given explicitly rather than left to React Flow's own default, so
              // `openingViewport` (review fix round 2, item 1, replacing round 1's Ruling T10-2)
              // always decides against the same minimum this canvas itself is bound by.
              minZoom={MIN_ZOOM}
              // A reader reads this graph; they do not draw one, and they do not take a module
              // out of it either - the delete key would otherwise remove what it is pointing at
              // until the next revision put it back.
              nodesConnectable={false}
              deleteKeyCode={null}
              // The node is a box around a button: React Flow's own tab stop in front of it
              // carries no name and would put two stops in the way of every module.
              nodesFocusable={false}
              // Ruling 2: above VISIBLE_ONLY_ABOVE modules, drawing every one regardless of the
              // viewport costs enough that it is left to React Flow's own culling; below it,
              // drawing them all is free enough that a reader should never meet one appear late
              // while panning.
              onlyRenderVisibleElements={visibleOnly(graph.modules.length)}
            >
              <Background />
              {/* Tidy and Fit are this canvas's controls, named above it. React Flow's lock would
                  write dragging and connecting back into its own store, past the props here, and
                  its fit-view icon is Fit again without a name worth reading. */}
              <Controls showInteractive={false} showFitView={false} />
            </ReactFlow>
          )}
        </section>
      </div>
      {variable !== undefined ? (
        <VariablePanel
          key={variable}
          name={variable}
          // No one component is in view on this screen, so there is no file to offer a removal
          // from - Task 7's optional prop on `VariablePanelView` then draws no offer at all.
          file={undefined}
          revision={revision}
          stopped={stopped}
          focusPicker={null}
          onClose={() => onVariable(undefined)}
          onUndeclared={() => {
            setUndeclared(variable);
            onVariable(undefined);
          }}
          onOpenType={onOpenType}
          onOpenConstant={onOpenConstant}
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
