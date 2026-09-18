import { Panel } from "./Panel";

export default { title: "UI / Panel" };

export const WithContent = () => (
  <Panel
    title="ValueA"
    meta="measurement · uint8 · produced by SensorHub"
    onClose={() => undefined}
  >
    <p>What the panel holds goes here.</p>
  </Panel>
);
