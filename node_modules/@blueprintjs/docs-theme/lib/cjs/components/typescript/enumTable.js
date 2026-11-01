"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EnumTable = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const common_1 = require("../../common");
const context_1 = require("../../common/context");
const modifierTable_1 = require("../modifierTable");
const apiHeader_1 = require("./apiHeader");
const deprecatedTag_1 = require("./deprecatedTag");
const EnumTable = props => {
    const { renderBlock } = (0, react_1.useContext)(context_1.DocumentationContext);
    const renderPropRow = (0, react_1.useCallback)((entry) => {
        const { flags, name } = entry;
        const classes = (0, classnames_1.default)("docs-prop-name", {
            "docs-prop-is-deprecated": !!flags?.isDeprecated,
            "docs-prop-is-internal": !flags?.isExternal,
        });
        // this is inside RUNNING_TEXT
        /* eslint-disable @blueprintjs/html-components */
        return ((0, jsx_runtime_1.jsxs)("tr", { children: [(0, jsx_runtime_1.jsx)("td", { className: classes, children: (0, jsx_runtime_1.jsx)("code", { children: name }) }), (0, jsx_runtime_1.jsxs)("td", { className: "docs-prop-details", children: [(0, jsx_runtime_1.jsx)("code", { className: "docs-prop-type", children: (0, jsx_runtime_1.jsx)("strong", { children: entry.defaultValue }) }), (0, jsx_runtime_1.jsx)("div", { className: "docs-prop-description", children: renderBlock(entry.documentation) }), (0, jsx_runtime_1.jsx)("div", { className: "docs-prop-tags", children: (0, jsx_runtime_1.jsx)(deprecatedTag_1.DeprecatedTag, { isDeprecated: flags?.isDeprecated }) })] })] }, name));
    }, [renderBlock]);
    return ((0, jsx_runtime_1.jsxs)("div", { className: (0, classnames_1.default)("docs-modifiers", props.className), children: [(0, jsx_runtime_1.jsx)(apiHeader_1.ApiHeader, { ...props.data }), renderBlock(props.data.documentation), (0, jsx_runtime_1.jsx)(modifierTable_1.ModifierTable, { emptyMessage: "This enum is empty.", title: "Members", children: props.data.members.map(renderPropRow) })] }));
};
exports.EnumTable = EnumTable;
exports.EnumTable.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.EnumTable`;
//# sourceMappingURL=enumTable.js.map