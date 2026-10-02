/**
 * A module's own box size on the canvas - shared by `laidOut` and `ranked` (`./layout.ts`, which
 * pulls dagre in and is reachable only from the worker) and `initialViewport` (`./canvas.ts`,
 * reachable from the main bundle, which must not pull dagre in - review fix round 1, Minor 2).
 * Neither of those two needs anything else the other does, so these live in a file of their own
 * rather than in either.
 */
export const NODE_WIDTH = 180;
export const NODE_HEIGHT = 48;
