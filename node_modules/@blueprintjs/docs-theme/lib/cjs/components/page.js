"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Page = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const core_1 = require("@blueprintjs/core");
const block_1 = require("./block");
const Page = ({ page, renderActions, tagRenderers }) => {
    // apply running text styles to blocks in pages (but not on blocks in examples)
    const pageContents = (0, block_1.renderBlock)(page, tagRenderers, core_1.Classes.TEXT_LARGE);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "docs-page", "data-page-id": page.route, children: [renderActions && (0, jsx_runtime_1.jsx)("div", { className: "docs-page-actions", children: renderActions(page) }), pageContents] }));
};
exports.Page = Page;
//# sourceMappingURL=page.js.map