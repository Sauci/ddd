/**
 * A module's own box size on the canvas - shared by `laidOut` and `ranked` (`./layout.ts`, which
 * pulls dagre in and is reachable only from the worker) and by `./canvas.ts` - each node's
 * `measured` size and handles (`nodesOf`, `handlesOf`) and the bounds `openingViewport` fits
 * (`boundsOf`) - which the main bundle reaches and which must not pull dagre in (review fix round
 * 1, Minor 2). Neither file needs anything else of the other's when it runs, so these live in a
 * file of their own rather than in either.
 */
export const NODE_WIDTH = 180;
export const NODE_HEIGHT = 48;
