import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";

import "./styles/shared.css";
import "./styles/app.css";
import IconSprite from "./components/IconSprite";
import Shell from "./components/Shell";

import Home from "./pages/Home";
import Predictions from "./pages/Predictions";
import Financial from "./pages/Financial";
import MapsPage from "./pages/MapsPage";
import Monitoring from "./pages/Monitoring";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <IconSprite />
    <HashRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/financial" element={<Financial />} />
          <Route path="/maps" element={<MapsPage />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </HashRouter>
  </React.StrictMode>
);
