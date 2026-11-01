"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TypeAliasTable = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const common_1 = require("../../common");
const context_1 = require("../../common/context");
const apiHeader_1 = require("./apiHeader");
const TypeAliasTable = ({ className, data }) => {
    const { renderBlock, renderType } = (0, react_1.useContext)(context_1.DocumentationContext);
    const aliases = data.type.split(" | ").map((type, i) => ((0, jsx_runtime_1.jsxs)("div", { children: [i === 0 ? "=" : "|", " ", renderType(type)] }, i)));
    return ((0, jsx_runtime_1.jsxs)("div", { className: (0, classnames_1.default)("docs-modifiers", className), children: [(0, jsx_runtime_1.jsx)(apiHeader_1.ApiHeader, { ...data }), renderBlock(data.documentation), (0, jsx_runtime_1.jsx)("div", { className: "docs-type-alias docs-code", children: aliases })] }));
};
exports.TypeAliasTable = TypeAliasTable;
exports.TypeAliasTable.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.TypeAliasTable`;
//# sourceMappingURL=typeAliasTable.js.map