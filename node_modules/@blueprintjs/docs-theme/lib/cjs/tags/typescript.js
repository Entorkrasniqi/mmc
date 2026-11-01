"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TypescriptExample = void 0;
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
const react_1 = require("react");
const common_1 = require("../common");
const context_1 = require("../common/context");
const enumTable_1 = require("../components/typescript/enumTable");
const interfaceTable_1 = require("../components/typescript/interfaceTable");
const typeAliasTable_1 = require("../components/typescript/typeAliasTable");
const TypescriptExample = ({ className, value }) => {
    const { getDocsData } = (0, react_1.useContext)(context_1.DocumentationContext);
    const { typescript } = getDocsData();
    if (typescript == null || typescript[value] == null) {
        return null;
    }
    const member = typescript[value];
    if (member === undefined) {
        throw new Error(`Unknown @interface ${value}`);
    }
    else if ((0, client_1.isTsClass)(member) || (0, client_1.isTsInterface)(member)) {
        return (0, jsx_runtime_1.jsx)(interfaceTable_1.InterfaceTable, { className: className, data: member, title: "Props" });
    }
    else if ((0, client_1.isTsEnum)(member)) {
        return (0, jsx_runtime_1.jsx)(enumTable_1.EnumTable, { className: className, data: member });
    }
    else if ((0, client_1.isTsTypeAlias)(member)) {
        return (0, jsx_runtime_1.jsx)(typeAliasTable_1.TypeAliasTable, { className: className, data: member });
    }
    else {
        throw new Error(`"@interface ${value}": unknown member kind "${member.kind}"`);
    }
};
exports.TypescriptExample = TypescriptExample;
exports.TypescriptExample.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.TypescriptExample`;
//# sourceMappingURL=typescript.js.map