import { jsx as _jsx } from "react/jsx-runtime";
import classNames from "classnames";
import { createElement } from "react";
import { Classes, Code, H3 } from "@blueprintjs/core";
export function renderBlock(
/** the block to render */
block, 
/** known tag renderers */
tagRenderers, 
/** class names to apply to element wrapping string content. */
textClassName) {
    if (block === undefined) {
        return null;
    }
    const textClasses = classNames(Classes.RUNNING_TEXT, textClassName);
    const contents = block.contents.map((node, i) => {
        if (typeof node === "string") {
            return _jsx("div", { className: textClasses, dangerouslySetInnerHTML: { __html: node } }, i);
        }
        try {
            const renderer = tagRenderers[node.tag];
            if (renderer === undefined) {
                throw new Error(`Unknown @tag: ${node.tag}`);
            }
            return createElement(renderer, { ...node, key: i });
        }
        catch (ex) {
            console.error(ex.message);
            return (_jsx(H3, { children: _jsx(Code, { children: ex.message }) }, `__error-${i}`));
        }
    });
    return _jsx("div", { className: "docs-section", children: contents });
}
//# sourceMappingURL=block.js.map