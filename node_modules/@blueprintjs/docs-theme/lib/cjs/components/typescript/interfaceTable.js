"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.InterfaceTable = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2017 Palantir Technologies, Inc. All rights reserved.
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
// rendered inside RUNNING_TEXT
/* eslint-disable @blueprintjs/html-components */
const InterfaceTable = ({ className, data, title }) => {
    const { renderBlock, renderType } = (0, react_1.useContext)(context_1.DocumentationContext);
    const renderPropRow = (0, react_1.useCallback)((entry) => {
        const { flags, name, inheritedFrom } = entry;
        const { documentation } = (0, client_1.isTsProperty)(entry) ? entry : entry.signatures[0];
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
        const typeInfo = (0, client_1.isTsProperty)(entry) ? ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)("strong", { children: renderType(entry.type) }), (0, jsx_runtime_1.jsx)(TsPropertyDefaultValue, { entry: entry })] })) : ((0, jsx_runtime_1.jsx)(jsx_runtime_1.Fragment, { children: (0, jsx_runtime_1.jsx)("strong", { children: renderType(entry.signatures[0].type) }) }));
        return ((0, jsx_runtime_1.jsxs)("tr", { children: [(0, jsx_runtime_1.jsx)("td", { className: classes, children: (0, jsx_runtime_1.jsx)("code", { children: name }) }), (0, jsx_runtime_1.jsxs)("td", { className: "docs-prop-details", children: [(0, jsx_runtime_1.jsx)("code", { className: "docs-prop-type", children: typeInfo }), (0, jsx_runtime_1.jsx)("div", { className: "docs-prop-description", children: documentation && renderBlock(documentation) }), (0, jsx_runtime_1.jsxs)("div", { className: "docs-prop-tags", children: [!flags?.isOptional && (0, jsx_runtime_1.jsx)(core_1.Tag, { children: "Required", intent: core_1.Intent.SUCCESS, minimal: true }), (0, jsx_runtime_1.jsx)(deprecatedTag_1.DeprecatedTag, { isDeprecated: flags?.isDeprecated }), inheritedFrom && ((0, jsx_runtime_1.jsxs)(core_1.Tag, { minimal: true, children: ["Inherited from ", (0, jsx_runtime_1.jsx)("code", { children: renderType(inheritedFrom) })] }))] })] })] }, name));
    }, [renderBlock, renderType]);
    const renderIndexSignature = (0, react_1.useCallback)((entry) => {
        if (entry == null) {
            return null;
        }
        // HACKHACK: Documentalist's indexSignature support isn't _great_, but it's certainly _good enough_
        // entry.type looks like "{ [name: string]: (date: Date) => boolean }"
        const [signature, returnType] = entry.type.slice(2, -2).split("]: ");
        return ((0, jsx_runtime_1.jsxs)("tr", { children: [(0, jsx_runtime_1.jsx)("td", { className: "docs-prop-name", children: (0, jsx_runtime_1.jsxs)("code", { children: [renderType(signature), "]"] }) }), (0, jsx_runtime_1.jsxs)("td", { className: "docs-prop-details", children: [(0, jsx_runtime_1.jsx)("code", { className: "docs-prop-type", children: renderType(returnType) }), (0, jsx_runtime_1.jsx)("div", { className: "docs-prop-description", children: renderBlock(entry.documentation) })] })] }, entry.name));
    }, [renderBlock, renderType]);
    const propRows = [...data.properties, ...data.methods]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(renderPropRow);
    return ((0, jsx_runtime_1.jsxs)("div", { className: (0, classnames_1.default)("docs-modifiers", className), children: [(0, jsx_runtime_1.jsx)(apiHeader_1.ApiHeader, { ...data }), renderBlock(data.documentation), (0, jsx_runtime_1.jsxs)(modifierTable_1.ModifierTable, { emptyMessage: "This interface is empty.", title: title, children: [propRows, renderIndexSignature(data.indexSignature)] })] }));
};
exports.InterfaceTable = InterfaceTable;
exports.InterfaceTable.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.InterfaceTable`;
function TsPropertyDefaultValue({ entry }) {
    let { defaultValue } = entry;
    if (defaultValue == null) {
        return null;
    }
    // HACKHACK: workaround for https://github.com/palantir/documentalist/issues/245
    // extract code snippet if it is wrapped in some extra markup
    const codeSnippetMatches = defaultValue.match(/```ts\s(.*)\s```/);
    if (codeSnippetMatches != null) {
        defaultValue = codeSnippetMatches[1].trim();
    }
    return (0, jsx_runtime_1.jsx)("em", { className: (0, classnames_1.default)("docs-prop-default", core_1.Classes.TEXT_MUTED), children: defaultValue });
}
//# sourceMappingURL=interfaceTable.js.map