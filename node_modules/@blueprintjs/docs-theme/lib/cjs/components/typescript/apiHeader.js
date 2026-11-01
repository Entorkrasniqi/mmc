"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApiHeader = void 0;
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
const common_1 = require("../../common");
const context_1 = require("../../common/context");
const ApiHeader = props => {
    const { renderType, renderViewSourceLinkText } = (0, react_1.useContext)(context_1.DocumentationContext);
    let inheritance = "";
    if ((0, client_1.isTsClass)(props) || (0, client_1.isTsInterface)(props)) {
        const extendsTypes = maybeJoinArray("extends", props.extends);
        const implementsTypes = maybeJoinArray("implements", props.implements);
        inheritance = renderType(`${extendsTypes} ${implementsTypes}`);
    }
    return ((0, jsx_runtime_1.jsxs)("div", { className: "docs-interface-header", children: [(0, jsx_runtime_1.jsxs)("div", { className: "docs-interface-name", children: [(0, jsx_runtime_1.jsx)("small", { children: props.kind }), " ", props.name, " ", (0, jsx_runtime_1.jsx)("small", { children: inheritance })] }), (0, jsx_runtime_1.jsx)("small", { className: "docs-package-name", children: (0, jsx_runtime_1.jsx)("a", { href: props.sourceUrl, target: "_blank", children: renderViewSourceLinkText(props) }) }), props.children] }));
};
exports.ApiHeader = ApiHeader;
exports.ApiHeader.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.ApiHeader`;
function maybeJoinArray(title, array) {
    if (array == null || array.length === 0) {
        return "";
    }
    return `${title} ${array.join(", ")}`;
}
//# sourceMappingURL=apiHeader.js.map