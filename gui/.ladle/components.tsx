import type { GlobalProvider } from "@ladle/react";
import "../src/styles/tokens.css";
import "../src/styles/app.css";
import "../src/styles/ui.css";

export const Provider: GlobalProvider = ({ children }) => (
  <div className="app story">{children}</div>
);
