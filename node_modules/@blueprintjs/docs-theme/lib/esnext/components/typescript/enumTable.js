import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import classNames from "classnames";
import { useCallback, useContext } from "react";
import { COMPONENT_DISPLAY_NAMESPACE } from "../../common";
import { DocumentationContext } from "../../common/context";
import { ModifierTable } from "../modifierTable";
import { ApiHeader } from "./apiHeader";
import { DeprecatedTag } from "./deprecatedTag";
export const EnumTable = props => {
    const { renderBlock } = useContext(DocumentationContext);
    const renderPropRow = useCallback((entry) => {
        const { flags, name } = entry;
        const classes = classNames("docs-prop-name", {
            "docs-prop-is-deprecated": !!flags?.isDeprecated,
            "docs-prop-is-internal": !flags?.isExternal,
        });
        // this is inside RUNNING_TEXT
        /* eslint-disable @blueprintjs/html-components */
        return (_jsxs("tr", { children: [_jsx("td", { className: classes, children: _jsx("code", { children: name }) }), _jsxs("td", { className: "docs-prop-details", children: [_jsx("code", { className: "docs-prop-type", children: _jsx("strong", { children: entry.defaultValue }) }), _jsx("div", { className: "docs-prop-description", children: renderBlock(entry.documentation) }), _jsx("div", { className: "docs-prop-tags", children: _jsx(DeprecatedTag, { isDeprecated: flags?.isDeprecated }) })] })] }, name));
    }, [renderBlock]);
    return (_jsxs("div", { className: classNames("docs-modifiers", props.className), children: [_jsx(ApiHeader, { ...props.data }), renderBlock(props.data.documentation), _jsx(ModifierTable, { emptyMessage: "This enum is empty.", title: "Members", children: props.data.members.map(renderPropRow) })] }));
};
EnumTable.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.EnumTable`;
//# sourceMappingURL=enumTable.js.map