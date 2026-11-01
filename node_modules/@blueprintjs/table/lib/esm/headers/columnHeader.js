import { jsx as _jsx } from "react/jsx-runtime";
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
import classNames from "classnames";
import { Component } from "react";
import * as Classes from "../common/classes";
import { Utils } from "../common/index";
import { Orientation } from "../interactions/resizeHandle";
import { RegionCardinality, Regions } from "../regions";
import { ColumnHeaderCell } from "./columnHeaderCell";
import { Header } from "./header";
export class ColumnHeader extends Component {
    static defaultProps = {
        isReorderable: false,
        isResizable: true,
        loading: false,
    };
    componentDidMount() {
        this.props.onMount?.("column");
    }
    render() {
        const { 
        // from ColumnHeaderProps
        cellRenderer: renderHeaderCell, onColumnWidthChanged, 
        // from ColumnWidths
        minColumnWidth: minSize, maxColumnWidth: maxSize, defaultColumnWidth, 
        // from ColumnIndices
        columnIndexStart: indexStart, columnIndexEnd: indexEnd, 
        // from HeaderProps
        ...spreadableProps } = this.props;
        return (_jsx(Header, { convertPointToIndex: this.convertPointToColumn, fullRegionCardinality: RegionCardinality.FULL_COLUMNS, getCellExtremaClasses: this.getCellExtremaClasses, getCellIndexClass: Classes.columnCellIndexClass, getCellSize: this.getColumnWidth, getDragCoordinate: this.getDragCoordinate, getIndexClass: Classes.columnIndexClass, getMouseCoordinate: this.getMouseCoordinate, ghostCellRenderer: this.renderGhostCell, handleResizeDoubleClick: this.handleResizeDoubleClick, handleResizeEnd: this.handleResizeEnd, handleSizeChanged: this.handleSizeChanged, headerCellIsReorderablePropName: "enableColumnReordering", headerCellIsSelectedPropName: "isColumnSelected", headerCellRenderer: renderHeaderCell, indexEnd: indexEnd, indexStart: indexStart, isCellSelected: this.isCellSelected, isGhostIndex: this.isGhostIndex, maxSize: maxSize, minSize: minSize, resizeOrientation: Orientation.VERTICAL, selectedRegions: [], toRegion: this.toRegion, wrapCells: this.wrapCells, ...spreadableProps }));
    }
    wrapCells = (cells) => {
        const { columnIndexStart, grid } = this.props;
        const tableWidth = grid.getRect().width;
        const scrollLeftCorrection = this.props.grid.getCumulativeWidthBefore(columnIndexStart);
        const style = {
            // only header cells in view will render, but we need to reposition them to stay in view
            // as we scroll horizontally.
            transform: `translateX(${scrollLeftCorrection || 0}px)`,
            // reduce the width to clamp the sliding window as we approach the final headers; otherwise,
            // we'll have tons of useless whitespace at the end.
            width: tableWidth - scrollLeftCorrection,
        };
        const classes = classNames(Classes.TABLE_THEAD, Classes.TABLE_COLUMN_HEADER_TR);
        // add a wrapper set to the full-table width to ensure container styles stretch from the first
        // cell all the way to the last
        return (_jsx("div", { style: { width: tableWidth }, children: _jsx("div", { style: style, className: classes, ref: this.props.measurableElementRef, children: cells }) }));
    };
    convertPointToColumn = (clientXOrY, useMidpoint) => {
        return this.props.locator.convertPointToColumn(clientXOrY, useMidpoint);
    };
    getCellExtremaClasses = (index, indexEnd) => {
        return this.props.grid.getExtremaClasses(0, index, 1, indexEnd);
    };
    getColumnWidth = (index) => {
        return this.props.grid.getColumnRect(index).width;
    };
    getDragCoordinate = (clientCoords) => {
        return clientCoords[0]; // x-coordinate
    };
    getMouseCoordinate = (event) => {
        return event.clientX;
    };
    handleResizeEnd = (index, size) => {
        this.props.onResizeGuide(null);
        this.props.onColumnWidthChanged(index, size);
    };
    handleResizeDoubleClick = (index) => {
        const { minColumnWidth, maxColumnWidth } = this.props;
        const width = this.props.locator.getWidestVisibleCellInColumn(index);
        const clampedWidth = Utils.clamp(width, minColumnWidth, maxColumnWidth);
        this.props.onResizeGuide(null);
        this.props.onColumnWidthChanged(index, clampedWidth);
    };
    handleSizeChanged = (index, size) => {
        const rect = this.props.grid.getColumnRect(index);
        this.props.onResizeGuide([rect.left + size]);
    };
    isCellSelected = (index) => {
        return Regions.hasFullColumn(this.props.selectedRegions, index);
    };
    isGhostIndex = (index) => {
        return this.props.grid.isGhostIndex(-1, index);
    };
    renderGhostCell = (index, extremaClasses) => {
        const { grid, loading } = this.props;
        const rect = grid.getGhostCellRect(0, index);
        const style = {
            flexBasis: `${rect.width}px`,
            width: `${rect.width}px`,
        };
        return (_jsx(ColumnHeaderCell, { className: classNames(extremaClasses), index: index, loading: loading, style: style }, Classes.columnIndexClass(index)));
    };
    toRegion = (index1, index2) => {
        return Regions.column(index1, index2);
    };
}
//# sourceMappingURL=columnHeader.js.map