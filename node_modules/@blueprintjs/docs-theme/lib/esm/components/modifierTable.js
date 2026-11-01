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
import classNames from "classnames";
import { Children } from "react";
import { Classes, HTMLTable } from "@blueprintjs/core";
export const ModifierTable = ({ children, descriptionTitle = "Description", emptyMessage, title, }) => (_jsx("div", { className: classNames("docs-modifiers-table", Classes.RUNNING_TEXT), children: _jsxs(HTMLTable, { children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: title }), _jsx("th", { children: descriptionTitle })] }) }), _jsx("tbody", { children: isEmpty(children) ? renderEmptyState(emptyMessage) : children })] }) }));
function isEmpty(children) {
    const array = Children.toArray(children);
    return array.length === 0 || array.filter(item => !!item).length === 0;
}
function renderEmptyState(message = "Nothing here.") {
    return (_jsx("tr", { children: _jsx("td", { colSpan: 2, children: _jsx("em", { className: Classes.TEXT_MUTED, children: message }) }) }));
}
//# sourceMappingURL=modifierTable.js.map