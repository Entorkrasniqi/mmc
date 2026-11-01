import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Classes } from "@blueprintjs/core";
import { renderBlock } from "./block";
export const Page = ({ page, renderActions, tagRenderers }) => {
    // apply running text styles to blocks in pages (but not on blocks in examples)
    const pageContents = renderBlock(page, tagRenderers, Classes.TEXT_LARGE);
    return (_jsxs("div", { className: "docs-page", "data-page-id": page.route, children: [renderActions && _jsx("div", { className: "docs-page-actions", children: renderActions(page) }), pageContents] }));
};
//# sourceMappingURL=page.js.map