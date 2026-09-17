import { createRoot } from "react-dom/client";

const root = document.getElementById("root");
if (root === null) throw new Error("index.html has no #root element");
createRoot(root).render(<p>ddd gui</p>);
