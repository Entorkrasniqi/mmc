import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { isTsClass, isTsInterface } from "@documentalist/client";
import { useContext } from "react";
import { COMPONENT_DISPLAY_NAMESPACE } from "../../common";
import { DocumentationContext } from "../../common/context";
export const ApiHeader = props => {
    const { renderType, renderViewSourceLinkText } = useContext(DocumentationContext);
    let inheritance = "";
    if (isTsClass(props) || isTsInterface(props)) {
        const extendsTypes = maybeJoinArray("extends", props.extends);
        const implementsTypes = maybeJoinArray("implements", props.implements);
        inheritance = renderType(`${extendsTypes} ${implementsTypes}`);
    }
    return (_jsxs("div", { className: "docs-interface-header", children: [_jsxs("div", { className: "docs-interface-name", children: [_jsx("small", { children: props.kind }), " ", props.name, " ", _jsx("small", { children: inheritance })] }), _jsx("small", { className: "docs-package-name", children: _jsx("a", { href: props.sourceUrl, target: "_blank", children: renderViewSourceLinkText(props) }) }), props.children] }));
};
ApiHeader.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.ApiHeader`;
function maybeJoinArray(title, array) {
    if (array == null || array.length === 0) {
        return "";
    }
    return `${title} ${array.join(", ")}`;
}
//# sourceMappingURL=apiHeader.js.map