import { BlueprintProvider } from "@blueprintjs/core";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/datetime/lib/css/blueprint-datetime.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import "@blueprintjs/select/lib/css/blueprint-select.css";
import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { SessionProvider } from "./Session";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BlueprintProvider>
      <SessionProvider>
        <App />
      </SessionProvider>
    </BlueprintProvider>
  </React.StrictMode>,
);
