import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { signInFrom } from "./api/signIn";
import { App } from "./app/App";
import { askSheetsAgain } from "./app/sheets";
import "@xyflow/react/dist/style.css";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/ui.css";

const root = document.getElementById("root");
if (root === null) throw new Error("index.html has no #root element");

const client = new QueryClient({
  // The server is on loopback: a browser's `offline` event says nothing of it, so neither a read
  // nor a write waits for the network to be said back.
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, networkMode: "always" },
    mutations: { networkMode: "always" },
  },
});

// Signed in, and every stylesheet the network failed asked for once more, before anything is
// rendered: no ask goes out without the token, and the page is not drawn unstyled for one lost
// request. Rendered however either ends, so that one that throws still draws the page.
void Promise.allSettled([
  signInFrom(window.location, window.history),
  askSheetsAgain(document),
]).then(() => {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
});
