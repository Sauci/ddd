import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";

/**
 * Everything the canvas hands one module's node.
 *
 * `onOpen` takes the module's path - the node's own id - because that is what the component page
 * is addressed by; the path is never shown, only the name is. `faded` is written by the canvas
 * and read by the stylesheet, so that hovering or searching can dim what is not a neighbour.
 */
export interface ModuleData extends Record<string, unknown> {
  name: string;
  loaded: boolean;
  errors: number;
  warnings: number;
  onOpen: (path: string) => void;
  faded: boolean;
}

/** One component on the canvas: its name as a button, and a badge when it holds findings. */
export function ModuleNode({ id, data }: NodeProps<Node<ModuleData>>) {
  const badge = data.errors > 0 ? data.errors : data.warnings;
  const tone = data.errors > 0 ? "error" : "warning";
  return (
    <div className={data.loaded ? "module" : "module unloaded"} data-faded={data.faded}>
      <Handle type="target" position={Position.Left} />
      <button type="button" className="name" onClick={() => data.onOpen(id)}>
        {data.loaded ? data.name : `${data.name} (not loaded)`}
      </button>
      {data.loaded && badge > 0 && (
        <span
          className={`badge ${tone}`}
          // A bare span takes no name, so the badge is announced as the one picture it is: a
          // number alone would not say what it counts.
          role="img"
          aria-label={`${badge} ${tone}${badge > 1 ? "s" : ""}`}
        >
          {badge}
        </span>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
