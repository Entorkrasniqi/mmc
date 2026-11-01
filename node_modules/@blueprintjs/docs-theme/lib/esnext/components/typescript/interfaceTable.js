import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
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
import { isTag, isTsProperty, } from "@documentalist/client";
import classNames from "classnames";
import { useCallback, useContext } from "react";
import { Classes, Intent, Tag } from "@blueprintjs/core";
import { COMPONENT_DISPLAY_NAMESPACE } from "../../common";
import { DocumentationContext } from "../../common/context";
import { ModifierTable } from "../modifierTable";
import { ApiHeader } from "./apiHeader";
import { DeprecatedTag } from "./deprecatedTag";
// rendered inside RUNNING_TEXT
/* eslint-disable @blueprintjs/html-components */
export const InterfaceTable = ({ className, data, title }) => {
    const { renderBlock, renderType } = useContext(DocumentationContext);
    const renderPropRow = useCallback((entry) => {
        const { flags, name, inheritedFrom } = entry;
        const { documentation } = isTsProperty(entry) ? entry : entry.signatures[0];
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
        const typeInfo = isTsProperty(entry) ? (_jsxs(_Fragment, { children: [_jsx("strong", { children: renderType(entry.type) }), _jsx(TsPropertyDefaultValue, { entry: entry })] })) : (_jsx(_Fragment, { children: _jsx("strong", { children: renderType(entry.signatures[0].type) }) }));
        return (_jsxs("tr", { children: [_jsx("td", { className: classes, children: _jsx("code", { children: name }) }), _jsxs("td", { className: "docs-prop-details", children: [_jsx("code", { className: "docs-prop-type", children: typeInfo }), _jsx("div", { className: "docs-prop-description", children: documentation && renderBlock(documentation) }), _jsxs("div", { className: "docs-prop-tags", children: [!flags?.isOptional && _jsx(Tag, { children: "Required", intent: Intent.SUCCESS, minimal: true }), _jsx(DeprecatedTag, { isDeprecated: flags?.isDeprecated }), inheritedFrom && (_jsxs(Tag, { minimal: true, children: ["Inherited from ", _jsx("code", { children: renderType(inheritedFrom) })] }))] })] })] }, name));
    }, [renderBlock, renderType]);
    const renderIndexSignature = useCallback((entry) => {
        if (entry == null) {
            return null;
        }
        // HACKHACK: Documentalist's indexSignature support isn't _great_, but it's certainly _good enough_
        // entry.type looks like "{ [name: string]: (date: Date) => boolean }"
        const [signature, returnType] = entry.type.slice(2, -2).split("]: ");
        return (_jsxs("tr", { children: [_jsx("td", { className: "docs-prop-name", children: _jsxs("code", { children: [renderType(signature), "]"] }) }), _jsxs("td", { className: "docs-prop-details", children: [_jsx("code", { className: "docs-prop-type", children: renderType(returnType) }), _jsx("div", { className: "docs-prop-description", children: renderBlock(entry.documentation) })] })] }, entry.name));
    }, [renderBlock, renderType]);
    const propRows = [...data.properties, ...data.methods]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(renderPropRow);
    return (_jsxs("div", { className: classNames("docs-modifiers", className), children: [_jsx(ApiHeader, { ...data }), renderBlock(data.documentation), _jsxs(ModifierTable, { emptyMessage: "This interface is empty.", title: title, children: [propRows, renderIndexSignature(data.indexSignature)] })] }));
};
InterfaceTable.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.InterfaceTable`;
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
    return _jsx("em", { className: classNames("docs-prop-default", Classes.TEXT_MUTED), children: defaultValue });
}
//# sourceMappingURL=interfaceTable.js.map