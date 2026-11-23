/**
 * Browser entry point mounting the React application.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { getToken } from "./api/client";
import "./state/theme.css";

const client = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 5_000 } } });
const root = document.getElementById("root");
if (!root) throw new Error("missing root element");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <App initialToken={getToken()} />
    </QueryClientProvider>
  </StrictMode>,
);
