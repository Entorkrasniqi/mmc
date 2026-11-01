"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RowHeaderCell = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2016 Palantir Technologies, Inc. All rights reserved.
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
const core_1 = require("@blueprintjs/core");
const Classes = tslib_1.__importStar(require("../common/classes"));
const loadableContent_1 = require("../common/loadableContent");
const headerCell_1 = require("./headerCell");
class RowHeaderCell extends core_1.AbstractPureComponent {
    render() {
        const { 
        // from RowHeaderCellProps
        enableRowReordering, isRowSelected, name, nameRenderer, 
        // from HeaderProps
        ...spreadableProps } = this.props;
        const defaultName = (0, jsx_runtime_1.jsx)("div", { className: Classes.TABLE_ROW_NAME_TEXT, children: name });
        const nameComponent = ((0, jsx_runtime_1.jsx)(loadableContent_1.LoadableContent, { loading: spreadableProps.loading ?? false, children: nameRenderer?.(name, spreadableProps.index) ?? defaultName }));
        return ((0, jsx_runtime_1.jsxs)(headerCell_1.HeaderCell, { isReorderable: this.props.enableRowReordering, isSelected: this.props.isRowSelected, ...spreadableProps, children: [(0, jsx_runtime_1.jsx)("div", { className: Classes.TABLE_ROW_NAME, children: nameComponent }), this.props.children, spreadableProps.loading ? undefined : spreadableProps.resizeHandle] }));
    }
}
exports.RowHeaderCell = RowHeaderCell;
//# sourceMappingURL=rowHeaderCell.js.map