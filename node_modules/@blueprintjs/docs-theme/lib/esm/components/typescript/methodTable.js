import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
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
import { isTag } from "@documentalist/client";
import classNames from "classnames";
import { useCallback, useContext } from "react";
import { Code, Intent, Tag } from "@blueprintjs/core";
import { COMPONENT_DISPLAY_NAMESPACE } from "../../common";
import { DocumentationContext } from "../../common/context";
import { ModifierTable } from "../modifierTable";
import { ApiHeader } from "./apiHeader";
import { DeprecatedTag } from "./deprecatedTag";
export const MethodTable = ({ className, data }) => {
    const { renderBlock, renderType } = useContext(DocumentationContext);
    const renderPropRow = useCallback((parameter) => {
        const { flags, name } = parameter;
        const { documentation } = parameter;
        // ignore props marked with `@internal` tag (this tag is in contents instead of in flags)
        if (documentation != null &&
            documentation.contents != null &&
            documentation.contents.some(val => isTag(val) && val.tag === "internal")) {
            return null;
        }
        const classes = classNames("docs-prop-name", {
            "docs-prop-is-deprecated": flags?.isDeprecated === true || typeof flags?.isDeprecated === "string",
            "docs-prop-is-internal": !flags?.isExternal,
            "docs-prop-is-required": !flags?.isOptional,
        });
        const typeInfo = (_jsx(_Fragment, { children: _jsx("strong", { children: renderType(parameter.type) }) }));
        return (_jsxs("tr", { children: [_jsx("td", { className: classes, children: _jsx(Code, { children: name }) }), _jsxs("td", { className: "docs-prop-details", children: [_jsx(Code, { className: "docs-prop-type", children: typeInfo }), _jsx("div", { className: "docs-prop-description", children: renderBlock(documentation) }), _jsxs("div", { className: "docs-prop-tags", children: [!flags?.isOptional && _jsx(Tag, { children: "Required", intent: Intent.SUCCESS, minimal: true }), _jsx(DeprecatedTag, { isDeprecated: flags?.isDeprecated })] })] })] }, name));
    }, [renderBlock, renderType]);
    const renderReturnSignature = useCallback((entry) => {
        if (entry == null) {
            return null;
        }
        return (_jsxs("tr", { children: [_jsx("td", { className: "docs-prop-name", children: _jsx(Code, { className: "docs-prop-type", children: renderType(entry.returnType) }) }), _jsx("td", { className: "docs-prop-details", children: _jsx("div", { className: "docs-prop-description", children: renderBlock(entry.documentation) }) })] }, entry.name));
    }, [renderBlock, renderType]);
    const propRows = [...data.signatures]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((entry) => entry.parameters.map(renderPropRow));
    return (_jsxs("div", { className: classNames("docs-modifiers", className), children: [_jsx(ApiHeader, { ...data }), _jsx(ModifierTable, { emptyMessage: "No return", title: "Returns", descriptionTitle: "", children: renderReturnSignature(data.signatures[0]) }), _jsx(ModifierTable, { emptyMessage: "This parameter is empty.", title: "Parameters", children: propRows })] }));
};
MethodTable.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.MethodTable`;
//# sourceMappingURL=methodTable.js.map