import { Button } from "./Button";

export default { title: "UI / Button" };

export const Kinds = () => (
  <div className="story-row">
    <Button variant="primary">Apply to 1 file</Button>
    <Button>Tidy</Button>
    <Button variant="link">Show changes</Button>
  </div>
);
