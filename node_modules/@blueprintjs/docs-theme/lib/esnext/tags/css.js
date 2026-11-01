import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import classNames from "classnames";
import { useCallback, useContext, useState } from "react";
import { Checkbox, Classes, Code } from "@blueprintjs/core";
import { COMPONENT_DISPLAY_NAMESPACE } from "../common";
import { DocumentationContext } from "../common/context";
import { Example } from "../components/example";
const MODIFIER_ATTR_REGEXP = /\{\{:modifier}}/g;
const MODIFIER_CLASS_REGEXP = /\{\{\.modifier}}/g;
export const CssExample = ({ value }) => {
    const { getDocsData } = useContext(DocumentationContext);
    const [activeModifiers, setActiveModifiers] = useState(new Set());
    const getModifiers = useCallback((prefix) => {
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
    const options = modifiers.map(modifier => (_jsxs(Checkbox, { checked: activeModifiers.has(modifier.name), onChange: getModifierToggleHandler(modifier.name), children: [_jsx(Code, { "data-modifier": modifier.name, children: modifier.name }), _jsx("div", { className: "docs-prop-description", dangerouslySetInnerHTML: { __html: modifier.documentation } })] }, modifier.name)));
    const classModifiers = getModifiers(".");
    const attrModifiers = getModifiers(":");
    const exampleHtml = markup
        .replace(MODIFIER_ATTR_REGEXP, attrModifiers)
        .replace(MODIFIER_CLASS_REGEXP, classModifiers);
    return (_jsxs(_Fragment, { children: [_jsx(Example, { id: reference, options: options.length > 0 ? options : false, html: exampleHtml }), _jsx("div", { className: classNames("docs-example-markup", Classes.RUNNING_TEXT), dangerouslySetInnerHTML: { __html: markupHtml } })] }));
};
CssExample.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.CssExample`;
//# sourceMappingURL=css.js.map