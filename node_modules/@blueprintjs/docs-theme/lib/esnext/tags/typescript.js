import { jsx as _jsx } from "react/jsx-runtime";
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
import { isTsClass, isTsEnum, isTsInterface, isTsTypeAlias, } from "@documentalist/client";
import { useContext } from "react";
import { COMPONENT_DISPLAY_NAMESPACE } from "../common";
import { DocumentationContext } from "../common/context";
import { EnumTable } from "../components/typescript/enumTable";
import { InterfaceTable } from "../components/typescript/interfaceTable";
import { TypeAliasTable } from "../components/typescript/typeAliasTable";
export const TypescriptExample = ({ className, value }) => {
    const { getDocsData } = useContext(DocumentationContext);
    const { typescript } = getDocsData();
    if (typescript == null || typescript[value] == null) {
        return null;
    }
    const member = typescript[value];
    if (member === undefined) {
        throw new Error(`Unknown @interface ${value}`);
    }
    else if (isTsClass(member) || isTsInterface(member)) {
        return _jsx(InterfaceTable, { className: className, data: member, title: "Props" });
    }
    else if (isTsEnum(member)) {
        return _jsx(EnumTable, { className: className, data: member });
    }
    else if (isTsTypeAlias(member)) {
        return _jsx(TypeAliasTable, { className: className, data: member });
    }
    else {
        throw new Error(`"@interface ${value}": unknown member kind "${member.kind}"`);
    }
};
TypescriptExample.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.TypescriptExample`;
//# sourceMappingURL=typescript.js.map