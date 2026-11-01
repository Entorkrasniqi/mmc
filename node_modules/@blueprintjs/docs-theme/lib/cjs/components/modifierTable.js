"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ModifierTable = void 0;
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
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const ModifierTable = ({ children, descriptionTitle = "Description", emptyMessage, title, }) => ((0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)("docs-modifiers-table", core_1.Classes.RUNNING_TEXT), children: (0, jsx_runtime_1.jsxs)(core_1.HTMLTable, { children: [(0, jsx_runtime_1.jsx)("thead", { children: (0, jsx_runtime_1.jsxs)("tr", { children: [(0, jsx_runtime_1.jsx)("th", { children: title }), (0, jsx_runtime_1.jsx)("th", { children: descriptionTitle })] }) }), (0, jsx_runtime_1.jsx)("tbody", { children: isEmpty(children) ? renderEmptyState(emptyMessage) : children })] }) }));
exports.ModifierTable = ModifierTable;
function isEmpty(children) {
    const array = react_1.Children.toArray(children);
    return array.length === 0 || array.filter(item => !!item).length === 0;
}
function renderEmptyState(message = "Nothing here.") {
    return ((0, jsx_runtime_1.jsx)("tr", { children: (0, jsx_runtime_1.jsx)("td", { colSpan: 2, children: (0, jsx_runtime_1.jsx)("em", { className: core_1.Classes.TEXT_MUTED, children: message }) }) }));
}
//# sourceMappingURL=modifierTable.js.map