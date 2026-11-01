/* !
 * (c) Copyright 2025 Palantir Technologies Inc. All rights reserved.
 */
/* eslint-disable sort-keys */
import LZString from "lz-string";
function compress(input) {
    return LZString.compressToBase64(input)
        .replace(/\+/g, `-`) // Convert '+' to '-'
        .replace(/\//g, `_`) // Convert '/' to '_'
        .replace(/=+$/, ``); // Remove ending '='
}
// source: https://github.com/codesandbox/codesandbox-importers/blob/d077bdf/packages/import-utils/src/api/define.ts
export function getParameters(parameters) {
    return compress(JSON.stringify(parameters));
}
const BLUEPRINT_PACKAGE_MAP = {
    "@blueprintjs/core": {
        package: "@blueprintjs/core",
        css: ["@blueprintjs/core/lib/css/blueprint.css"],
    },
    "@blueprintjs/icons": {
        package: "@blueprintjs/icons",
        css: ["@blueprintjs/icons/lib/css/blueprint-icons.css"],
    },
    "@blueprintjs/datetime": {
        package: "@blueprintjs/datetime",
        css: [
            "@blueprintjs/datetime/lib/css/blueprint-datetime.css",
            "@blueprintjs/select/lib/css/blueprint-select.css",
        ],
    },
    "@blueprintjs/select": {
        package: "@blueprintjs/select",
        css: ["@blueprintjs/select/lib/css/blueprint-select.css"],
    },
    "@blueprintjs/table": {
        package: "@blueprintjs/table",
        css: ["@blueprintjs/table/lib/css/table.css"],
    },
};
/**
 * Default dependencies that are always included
 */
const DEFAULT_DEPENDENCIES = {
    clsx: "latest",
    react: "^18",
    "react-dom": "^18",
    "react-scripts": "latest",
};
const DEFAULT_DEV_DEPENDENCIES = {
    "@types/react": "^18",
    "@types/react-dom": "^18",
    typescript: "latest",
};
/**
 * Extracts import statements from TypeScript/JavaScript code
 */
export function extractImports(code) {
    const importRegex = /import\s+(?:.*?\s+from\s+)?['"`]([^'"`]+)['"`]/g;
    const imports = [];
    let match;
    while ((match = importRegex.exec(code)) !== null) {
        imports.push(match[1]);
    }
    return imports;
}
/**
 * Converts import specifiers to npm package dependencies
 */
export function extractDependencies(imports) {
    const dependencies = { ...DEFAULT_DEPENDENCIES };
    for (const importPath of imports) {
        // Check if it's a Blueprint package
        if (BLUEPRINT_PACKAGE_MAP[importPath]) {
            dependencies[BLUEPRINT_PACKAGE_MAP[importPath].package] = "latest";
        }
        // Handle scoped packages (e.g., @blueprintjs/core)
        else if (importPath.startsWith("@")) {
            const scopedPackage = importPath.split("/").slice(0, 2).join("/");
            if (BLUEPRINT_PACKAGE_MAP[scopedPackage]) {
                dependencies[BLUEPRINT_PACKAGE_MAP[scopedPackage].package] = "latest";
            }
            else {
                // For non-Blueprint scoped packages, use latest
                dependencies[scopedPackage] = "latest";
            }
        }
        // Handle other npm packages (ignore relative imports)
        else if (!importPath.startsWith(".") && !importPath.startsWith("/")) {
            // Extract package name (handle sub-paths like 'lodash/get')
            const packageName = importPath.split("/")[0];
            dependencies[packageName] = "latest";
        }
    }
    return dependencies;
}
/**
 * Extracts CSS imports needed for the given import specifiers
 */
export function extractStylesheets(imports) {
    const stylesheets = new Set();
    // Always include core Blueprint styles
    stylesheets.add("@blueprintjs/core/lib/css/blueprint.css");
    stylesheets.add("@blueprintjs/icons/lib/css/blueprint-icons.css");
    for (const importPath of imports) {
        if (BLUEPRINT_PACKAGE_MAP[importPath]?.css) {
            BLUEPRINT_PACKAGE_MAP[importPath].css.forEach(css => stylesheets.add(css));
        }
        // Handle scoped packages
        else if (importPath.startsWith("@")) {
            const scopedPackage = importPath.split("/").slice(0, 2).join("/");
            if (BLUEPRINT_PACKAGE_MAP[scopedPackage]?.css) {
                BLUEPRINT_PACKAGE_MAP[scopedPackage].css.forEach(css => stylesheets.add(css));
            }
        }
    }
    return Array.from(stylesheets);
}
/**
 * Analyzes code and extracts all necessary information for sandbox generation
 */
export function analyzeCode(code) {
    const imports = extractImports(code);
    const dependencies = extractDependencies(imports);
    const stylesheets = extractStylesheets(imports);
    return {
        imports,
        dependencies,
        stylesheets,
    };
}
export const getHtml = ({ title }) => {
    return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>${title}</title>
    <meta name="viewport" content="initial-scale=1, width=device-width" />
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>`;
};
export const getIndex = (stylesheets, isDark = false) => {
    const defaultStylesheets = [
        "@blueprintjs/core/lib/css/blueprint.css",
        "@blueprintjs/icons/lib/css/blueprint-icons.css",
    ];
    const allStylesheets = stylesheets || defaultStylesheets;
    const cssImports = allStylesheets.map(css => `import "${css}";`).join("\n");
    return `import { Classes, FocusStyleManager } from "@blueprintjs/core";
    import clsx from "clsx";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import Demo from "./Demo";

${cssImports}
import "./styles.scss";

const IS_DARK = ${isDark};

FocusStyleManager.onlyShowFocusOnTabs();

const rootElement = document.getElementById("root")!;
const root = createRoot(rootElement);

root.render(
  <StrictMode>
    <div className={clsx("app", { [Classes.DARK]: IS_DARK })}>
      <Demo />
    </div>
  </StrictMode>
);
`;
};
export const getStyles = () => {
    return `@use "@blueprintjs/core/lib/scss/variables.scss" as bp;

*,
*::before,
*::after {
  box-sizing: border-box;
}

* {
  margin: 0;
}

.app {
  height: 100vh;
  padding: 2 * bp.$pt-grid-size;

  &.#{bp.$ns}-dark {
    background: bp.$dark-gray1;
  }
}

.group {
  display: flex;
  gap: 8px;
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.center {
  align-items: center;
}`;
};
export const getTsconfig = () => `{
  "compilerOptions": {
    "strict": true,
    "esModuleInterop": true,
    "lib": [
      "dom",
      "es2015"
    ],
    "jsx": "react-jsx"
  },
  "include": [
    "src"
  ]
}
`;
export const getpackageJson = (dependencies) => {
    const defaultDependencies = {
        "@blueprintjs/core": "latest",
        "@blueprintjs/icons": "latest",
        ...DEFAULT_DEPENDENCIES,
    };
    const allDependencies = dependencies || defaultDependencies;
    return JSON.stringify({
        private: true,
        dependencies: allDependencies,
        devDependencies: DEFAULT_DEV_DEPENDENCIES,
        scripts: {
            start: "react-scripts start",
            build: "react-scripts build",
            test: "react-scripts test",
            eject: "react-scripts eject",
        },
    }, null, 2);
};
//# sourceMappingURL=sandbox.js.map