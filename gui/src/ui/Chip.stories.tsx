import { Chip } from "./Chip";

export default { title: "UI / Chip" };

export const Tones = () => (
  <div className="story-row">
    <Chip tone="error">definition-mismatch</Chip>
    <Chip tone="warning">unused-output</Chip>
    <Chip tone="neutral">2 variables</Chip>
  </div>
);
