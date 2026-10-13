import "@fontsource/open-sans/hebrew-400.css";
import "@fontsource/open-sans/hebrew-600.css";
import "@fontsource/open-sans/hebrew-700.css";
import "@fontsource/open-sans/hebrew-800.css";
import "@fontsource/open-sans/latin-400.css";
import "@fontsource/open-sans/latin-700.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
