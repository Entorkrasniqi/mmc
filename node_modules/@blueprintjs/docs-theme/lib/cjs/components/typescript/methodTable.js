"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MethodTable = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2020 Palantir Technologies, Inc. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
const client_1 = require("@documentalist/client");
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const common_1 = require("../../common");
const context_1 = require("../../common/context");
const modifierTable_1 = require("../modifierTable");
const apiHeader_1 = require("./apiHeader");
const deprecatedTag_1 = require("./deprecatedTag");
const MethodTable = ({ className, data }) => {
    const { renderBlock, renderType } = (0, react_1.useContext)(context_1.DocumentationContext);
    const renderPropRow = (0, react_1.useCallback)((parameter) => {
        const { flags, name } = parameter;
        const { documentation } = parameter;
        // ignore props marked with `@internal` tag (this tag is in contents instead of in flags)
        if (documentation != null &&
            documentation.contents != null &&
            documentation.contents.some(val => (0, client_1.isTag)(val) && val.tag === "internal")) {
            return null;
        }
        const classes = (0, classnames_1.default)("docs-prop-name", {
            "docs-prop-is-deprecated": flags?.isDeprecated === true || typeof flags?.isDeprecated === "string",
            "docs-prop-is-internal": !flags?.isExternal,
            "docs-prop-is-required": !flags?.isOptional,
        });
        const typeInfo = ((0, jsx_runtime_1.jsx)(jsx_runtime_1.Fragment, { children: (0, jsx_runtime_1.jsx)("strong", { children: renderType(parameter.type) }) }));
        return ((0, jsx_runtime_1.jsxs)("tr", { children: [(0, jsx_runtime_1.jsx)("td", { className: classes, children: (0, jsx_runtime_1.jsx)(core_1.Code, { children: name }) }), (0, jsx_runtime_1.jsxs)("td", { className: "docs-prop-details", children: [(0, jsx_runtime_1.jsx)(core_1.Code, { className: "docs-prop-type", children: typeInfo }), (0, jsx_runtime_1.jsx)("div", { className: "docs-prop-description", children: renderBlock(documentation) }), (0, jsx_runtime_1.jsxs)("div", { className: "docs-prop-tags", children: [!flags?.isOptional && (0, jsx_runtime_1.jsx)(core_1.Tag, { children: "Required", intent: core_1.Intent.SUCCESS, minimal: true }), (0, jsx_runtime_1.jsx)(deprecatedTag_1.DeprecatedTag, { isDeprecated: flags?.isDeprecated })] })] })] }, name));
    }, [renderBlock, renderType]);
    const renderReturnSignature = (0, react_1.useCallback)((entry) => {
        if (entry == null) {
            return null;
        }
        return ((0, jsx_runtime_1.jsxs)("tr", { children: [(0, jsx_runtime_1.jsx)("td", { className: "docs-prop-name", children: (0, jsx_runtime_1.jsx)(core_1.Code, { className: "docs-prop-type", children: renderType(entry.returnType) }) }), (0, jsx_runtime_1.jsx)("td", { className: "docs-prop-details", children: (0, jsx_runtime_1.jsx)("div", { className: "docs-prop-description", children: renderBlock(entry.documentation) }) })] }, entry.name));
    }, [renderBlock, renderType]);
    const propRows = [...data.signatures]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((entry) => entry.parameters.map(renderPropRow));
    return ((0, jsx_runtime_1.jsxs)("div", { className: (0, classnames_1.default)("docs-modifiers", className), children: [(0, jsx_runtime_1.jsx)(apiHeader_1.ApiHeader, { ...data }), (0, jsx_runtime_1.jsx)(modifierTable_1.ModifierTable, { emptyMessage: "No return", title: "Returns", descriptionTitle: "", children: renderReturnSignature(data.signatures[0]) }), (0, jsx_runtime_1.jsx)(modifierTable_1.ModifierTable, { emptyMessage: "This parameter is empty.", title: "Parameters", children: propRows })] }));
};
exports.MethodTable = MethodTable;
exports.MethodTable.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.MethodTable`;
//# sourceMappingURL=methodTable.js.map