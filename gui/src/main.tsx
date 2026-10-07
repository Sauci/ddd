import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { signInFrom } from "./api/signIn";
import { App } from "./app/App";
import "@xyflow/react/dist/style.css";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/ui.css";

const root = document.getElementById("root");
if (root === null) throw new Error("index.html has no #root element");

const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

// Signed in before anything is rendered, so that no ask goes out without the token; rendered
// however the sign-in ends, so that one that throws still draws the page.
void signInFrom(window.location, window.history).finally(() => {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
});
