"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Method = void 0;
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
const methodTable_1 = require("../components/typescript/methodTable");
const Method = ({ className, value }) => {
    const { getDocsData } = (0, react_1.useContext)(context_1.DocumentationContext);
    const { typescript } = getDocsData();
    const member = typescript[value];
    if (member === undefined) {
        const possibleClass = value.split(".")[0];
        const possibleClassMethod = value.split(".")[1];
        const classMember = typescript[possibleClass];
        if ((0, client_1.isTsClass)(classMember) && possibleClassMethod) {
            const classMethod = classMember.methods.find(method => method.name === possibleClassMethod);
            if ((0, client_1.isTsMethod)(classMethod)) {
                return (0, jsx_runtime_1.jsx)(methodTable_1.MethodTable, { className: className, data: classMethod });
            }
        }
        throw new Error(`Unknown @method ${value}`);
    }
    else if ((0, client_1.isTsMethod)(member)) {
        return (0, jsx_runtime_1.jsx)(methodTable_1.MethodTable, { className: className, data: member });
    }
    else {
        throw new Error(`"@method ${value}": unknown member kind "${member.kind}"`);
    }
};
exports.Method = Method;
exports.Method.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.Method`;
//# sourceMappingURL=method.js.map