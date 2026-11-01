import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { AbstractPureComponent } from "@blueprintjs/core";
import * as Classes from "../common/classes";
import { LoadableContent } from "../common/loadableContent";
import { HeaderCell } from "./headerCell";
export class RowHeaderCell extends AbstractPureComponent {
    render() {
        const { 
        // from RowHeaderCellProps
        enableRowReordering, isRowSelected, name, nameRenderer, 
        // from HeaderProps
        ...spreadableProps } = this.props;
        const defaultName = _jsx("div", { className: Classes.TABLE_ROW_NAME_TEXT, children: name });
        const nameComponent = (_jsx(LoadableContent, { loading: spreadableProps.loading ?? false, children: nameRenderer?.(name, spreadableProps.index) ?? defaultName }));
        return (_jsxs(HeaderCell, { isReorderable: this.props.enableRowReordering, isSelected: this.props.isRowSelected, ...spreadableProps, children: [_jsx("div", { className: Classes.TABLE_ROW_NAME, children: nameComponent }), this.props.children, spreadableProps.loading ? undefined : spreadableProps.resizeHandle] }));
    }
}
//# sourceMappingURL=rowHeaderCell.js.map