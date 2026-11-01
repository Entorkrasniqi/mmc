"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CssExample = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const common_1 = require("../common");
const context_1 = require("../common/context");
const example_1 = require("../components/example");
const MODIFIER_ATTR_REGEXP = /\{\{:modifier}}/g;
const MODIFIER_CLASS_REGEXP = /\{\{\.modifier}}/g;
const CssExample = ({ value }) => {
    const { getDocsData } = (0, react_1.useContext)(context_1.DocumentationContext);
    const [activeModifiers, setActiveModifiers] = (0, react_1.useState)(new Set());
    const getModifiers = (0, react_1.useCallback)((prefix) => {
        return Array.from(activeModifiers.keys())
            .filter(mod => mod.charAt(0) === prefix)
            .map(mod => mod.slice(1))
            .join(" ");
    }, [activeModifiers]);
    const getModifierToggleHandler = (modifier) => {
        return () => {
            const newModifiers = new Set(activeModifiers);
            if (newModifiers.has(modifier)) {
                newModifiers.delete(modifier);
            }
            else {
                newModifiers.add(modifier);
            }
            setActiveModifiers(newModifiers);
        };
    };
    const { css } = getDocsData();
    if (css == null || css[value] == null) {
        return null;
    }
    const { markup, markupHtml, modifiers, reference } = css[value];
    const options = modifiers.map(modifier => ((0, jsx_runtime_1.jsxs)(core_1.Checkbox, { checked: activeModifiers.has(modifier.name), onChange: getModifierToggleHandler(modifier.name), children: [(0, jsx_runtime_1.jsx)(core_1.Code, { "data-modifier": modifier.name, children: modifier.name }), (0, jsx_runtime_1.jsx)("div", { className: "docs-prop-description", dangerouslySetInnerHTML: { __html: modifier.documentation } })] }, modifier.name)));
    const classModifiers = getModifiers(".");
    const attrModifiers = getModifiers(":");
    const exampleHtml = markup
        .replace(MODIFIER_ATTR_REGEXP, attrModifiers)
        .replace(MODIFIER_CLASS_REGEXP, classModifiers);
    return ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(example_1.Example, { id: reference, options: options.length > 0 ? options : false, html: exampleHtml }), (0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)("docs-example-markup", core_1.Classes.RUNNING_TEXT), dangerouslySetInnerHTML: { __html: markupHtml } })] }));
};
exports.CssExample = CssExample;
exports.CssExample.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.CssExample`;
//# sourceMappingURL=css.js.map