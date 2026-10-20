import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import { ProfileProvider } from "./profile";
import OpportunitiesPage from "./pages/Opportunities";
import RunPage from "./pages/Run";
import KnowledgeBasePage from "./pages/KnowledgeBase";
import ComparePage from "./pages/Compare";

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ProfileProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<OpportunitiesPage />} />
              <Route path="/runs/:runId" element={<RunPage />} />
              <Route path="/knowledge" element={<KnowledgeBasePage />} />
              <Route path="/compare" element={<ComparePage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ProfileProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
