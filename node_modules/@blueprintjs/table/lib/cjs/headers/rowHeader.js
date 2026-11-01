"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RowHeader = void 0;
exports.renderDefaultRowHeader = renderDefaultRowHeader;
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
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const Classes = tslib_1.__importStar(require("../common/classes"));
const resizeHandle_1 = require("../interactions/resizeHandle");
const regions_1 = require("../regions");
const header_1 = require("./header");
const rowHeaderCell_1 = require("./rowHeaderCell");
class RowHeader extends react_1.Component {
    static defaultProps = {
        rowHeaderCellRenderer: renderDefaultRowHeader,
    };
    componentDidMount() {
        this.props.onMount?.("row");
    }
    render() {
        const { 
        // from RowHeaderProps
        onRowHeightChanged, rowHeaderCellRenderer, 
        // from RowHeights
        minRowHeight: minSize, maxRowHeight: maxSize, defaultRowHeight, 
        // from RowIndices
        rowIndexStart: indexStart, rowIndexEnd: indexEnd, 
        // from HeaderProps
        ...spreadableProps } = this.props;
        return ((0, jsx_runtime_1.jsx)(header_1.Header, { convertPointToIndex: this.convertPointToRow, fullRegionCardinality: regions_1.RegionCardinality.FULL_ROWS, getCellExtremaClasses: this.getCellExtremaClasses, getCellIndexClass: Classes.rowCellIndexClass, getCellSize: this.getRowHeight, getDragCoordinate: this.getDragCoordinate, getIndexClass: Classes.rowIndexClass, getMouseCoordinate: this.getMouseCoordinate, ghostCellRenderer: this.renderGhostCell, handleResizeEnd: this.handleResizeEnd, handleSizeChanged: this.handleSizeChanged, headerCellIsReorderablePropName: "enableRowReordering", headerCellIsSelectedPropName: "isRowSelected", headerCellRenderer: rowHeaderCellRenderer, indexEnd: indexEnd, indexStart: indexStart, isCellSelected: this.isCellSelected, isGhostIndex: this.isGhostIndex, maxSize: maxSize, minSize: minSize, resizeOrientation: resizeHandle_1.Orientation.HORIZONTAL, selectedRegions: [], toRegion: this.toRegion, wrapCells: this.wrapCells, ...spreadableProps }));
    }
    wrapCells = (cells) => {
        const { rowIndexStart, grid } = this.props;
        const tableHeight = grid.getRect().height;
        const scrollTopCorrection = this.props.grid.getCumulativeHeightBefore(rowIndexStart);
        const style = {
            // reduce the height to clamp the sliding window as we approach the final headers; otherwise,
            // we'll have tons of useless whitespace at the end.
            height: tableHeight - scrollTopCorrection,
            // only header cells in view will render, but we need to reposition them to stay in view
            // as we scroll vertically.
            transform: `translateY(${scrollTopCorrection || 0}px)`,
        };
        // add a wrapper set to the full-table height to ensure container styles stretch from the first
        // cell all the way to the last
        return ((0, jsx_runtime_1.jsx)("div", { style: { height: tableHeight }, children: (0, jsx_runtime_1.jsx)("div", { className: Classes.TABLE_ROW_HEADERS_CELLS_CONTAINER, style: style, children: cells }) }));
    };
    convertPointToRow = (clientXOrY, useMidpoint) => {
        return this.props.locator?.convertPointToRow(clientXOrY, useMidpoint);
    };
    getCellExtremaClasses = (index, indexEnd) => {
        return this.props.grid.getExtremaClasses(index, 0, indexEnd, 1);
    };
    getRowHeight = (index) => {
        return this.props.grid.getRowRect(index).height;
    };
    getDragCoordinate = (clientCoords) => {
        return clientCoords[1]; // y-coordinate
    };
    getMouseCoordinate = (event) => {
        return event.clientY;
    };
    handleResizeEnd = (index, size) => {
        this.props.onResizeGuide(null);
        this.props.onRowHeightChanged(index, size);
    };
    handleSizeChanged = (index, size) => {
        const rect = this.props.grid.getRowRect(index);
        this.props.onResizeGuide([rect.top + size]);
    };
    isCellSelected = (index) => {
        return regions_1.Regions.hasFullRow(this.props.selectedRegions, index);
    };
    isGhostIndex = (index) => {
        return this.props.grid.isGhostIndex(index, -1);
    };
    renderGhostCell = (index, extremaClasses) => {
        const rect = this.props.grid.getGhostCellRect(index, 0);
        return ((0, jsx_runtime_1.jsx)(rowHeaderCell_1.RowHeaderCell, { className: (0, classnames_1.default)(extremaClasses), index: index, loading: this.props.loading, style: { height: `${rect.height}px` } }, Classes.rowIndexClass(index)));
    };
    toRegion = (index1, index2) => {
        // the `this` value is messed up for Regions.row, so we have to have a wrapper function here
        return regions_1.Regions.row(index1, index2);
    };
}
exports.RowHeader = RowHeader;
/**
 * A default implementation of `RowHeaderRenderer` that displays 1-indexed
 * numbers for each row.
 */
function renderDefaultRowHeader(rowIndex) {
    return (0, jsx_runtime_1.jsx)(rowHeaderCell_1.RowHeaderCell, { index: rowIndex, name: `${rowIndex + 1}` });
}
//# sourceMappingURL=rowHeader.js.map