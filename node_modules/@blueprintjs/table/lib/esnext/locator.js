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
import * as Classes from "./common/classes";
import { Grid } from "./common/grid";
import { Rect } from "./common/rect";
import { Utils } from "./common/utils";
export class LocatorImpl {
    tableElement;
    scrollContainerElement;
    cellContainerElement;
    static CELL_HORIZONTAL_PADDING = 10;
    grid;
    // these values affect how we map a mouse coordinate to a cell coordinate.
    // for instance, a click at (0px,0px) in the grid could map to an arbitrary
    // cell if table is scrolled, but it will always map to cell (0,0) if there
    // are active frozen rows and columns.
    numFrozenRows;
    numFrozenColumns;
    constructor(
    /* The root table element within which a click is deemed valid and relevant. */
    tableElement, 
    /* The scrollable element that wraps the cell container. */
    scrollContainerElement, 
    /* The element containing all body cells in the grid (excluding headers). */
    cellContainerElement) {
        this.tableElement = tableElement;
        this.scrollContainerElement = scrollContainerElement;
        this.cellContainerElement = cellContainerElement;
        this.numFrozenRows = 0;
        this.numFrozenColumns = 0;
    }
    // Setters
    // =======
    setGrid(grid) {
        this.grid = grid;
        return this;
    }
    setNumFrozenRows(numFrozenRows) {
        this.numFrozenRows = numFrozenRows;
        return this;
    }
    setNumFrozenColumns(numFrozenColumns) {
        this.numFrozenColumns = numFrozenColumns;
        return this;
    }
    // Getters
    // =======
    getViewportRect() {
        return new Rect(this.scrollContainerElement.scrollLeft || 0, this.scrollContainerElement.scrollTop || 0, this.scrollContainerElement.clientWidth, this.scrollContainerElement.clientHeight);
    }
    getWidestVisibleCellInColumn(columnIndex) {
        const columnCellSelector = this.getColumnCellSelector(columnIndex);
        const columnHeaderAndBodyCells = this.tableElement.querySelectorAll(columnCellSelector);
        let maxWidth = 0;
        for (let i = 0; i < columnHeaderAndBodyCells.length; i++) {
            const contentWidth = Utils.measureElementTextContent(columnHeaderAndBodyCells.item(i)).width;
            const cellWidth = Math.ceil(contentWidth) + LocatorImpl.CELL_HORIZONTAL_PADDING * 2;
            if (cellWidth > maxWidth) {
                maxWidth = cellWidth;
            }
        }
        return maxWidth;
    }
    getTallestVisibleCellInColumn(columnIndex) {
        // consider only body cells, hence the extra Classes.TABLE_CELL specificity
        const columnCellSelector = this.getColumnCellSelector(columnIndex);
        const columnBodyCells = this.tableElement.querySelectorAll(`${columnCellSelector}.${Classes.TABLE_CELL}`);
        let maxHeight = 0;
        for (let i = 0; i < columnBodyCells.length; i++) {
            const cell = columnBodyCells.item(i);
            const cellValue = cell.querySelector(`.${Classes.TABLE_TRUNCATED_VALUE}`);
            const cellTruncatedFormatText = cell.querySelector(`.${Classes.TABLE_TRUNCATED_FORMAT_TEXT}`);
            const cellTruncatedText = cell.querySelector(`.${Classes.TABLE_TRUNCATED_TEXT}`);
            let height = 0;
            if (cellValue != null) {
                height = cellValue.scrollHeight;
            }
            else if (cellTruncatedFormatText != null) {
                height = cellTruncatedFormatText.scrollHeight;
            }
            else if (cellTruncatedText != null) {
                height = cellTruncatedText.scrollHeight;
            }
            else {
                // it's not anything we recognize, just use the current height of the cell
                height = cell.scrollHeight;
            }
            if (height > maxHeight) {
                maxHeight = height;
            }
        }
        return maxHeight;
    }
    /**
     * Pass in an already-computed viewport rect here, if available, to reduce DOM reads.
     *
     * @returns whether the rendered rows overflow or exactly fit the visible viewport vertically, helpful for scrolling calculations
     */
    hasVerticalOverflowOrExactFit(columnHeaderHeight = Grid.MIN_COLUMN_HEADER_HEIGHT, viewportRect = this.getViewportRect()) {
        if (this.grid === undefined) {
            return false;
        }
        return this.grid.getHeight() >= viewportRect.height - columnHeaderHeight;
    }
    /**
     * Pass in an already-computed viewport rect here, if available, to reduce DOM reads.
     *
     * @returns whether the rendered columns overflow or exactly fit the visible viewport horizontally, helpful for scrolling calculations
     */
    hasHorizontalOverflowOrExactFit(rowHeaderWidth = Grid.MIN_ROW_HEADER_WIDTH, viewportRect = this.getViewportRect()) {
        if (this.grid === undefined) {
            return false;
        }
        return this.grid.getWidth() >= viewportRect.width - rowHeaderWidth;
    }
    // Converters
    // ==========
    convertPointToColumn(clientX, useMidpoint) {
        const tableRect = this.getTableRect();
        if (this.grid === undefined || !tableRect.containsX(clientX)) {
            return -1;
        }
        const gridX = this.toGridX(clientX);
        const limit = useMidpoint ? this.grid.numCols : this.grid.numCols - 1;
        const lookupFn = useMidpoint ? this.convertCellMidpointToClientX : this.convertCellIndexToClientX;
        return Utils.binarySearch(gridX, limit, lookupFn);
    }
    convertPointToRow(clientY, useMidpoint) {
        const tableRect = this.getTableRect();
        if (this.grid === undefined || !tableRect.containsY(clientY)) {
            return -1;
        }
        const gridY = this.toGridY(clientY);
        const limit = useMidpoint ? this.grid.numRows : this.grid.numRows - 1;
        const lookupFn = useMidpoint ? this.convertCellMidpointToClientY : this.convertCellIndexToClientY;
        return Utils.binarySearch(gridY, limit, lookupFn);
    }
    convertPointToCell(clientX, clientY) {
        const gridX = this.toGridX(clientX);
        const gridY = this.toGridY(clientY);
        const col = Utils.binarySearch(gridX, this.grid.numCols - 1, this.convertCellIndexToClientX);
        const row = Utils.binarySearch(gridY, this.grid.numRows - 1, this.convertCellIndexToClientY);
        return { col, row };
    }
    // Private helpers
    // ===============
    getColumnCellSelector(columnIndex) {
        // measure frozen columns in the LEFT quadrant; otherwise, they might
        // have been scrolled out of view, leading to wonky measurements (#1561)
        const isFrozenColumnIndex = columnIndex < this.numFrozenColumns;
        const quadrantClass = isFrozenColumnIndex ? Classes.TABLE_QUADRANT_LEFT : Classes.TABLE_QUADRANT_MAIN;
        const cellClass = Classes.columnCellIndexClass(columnIndex);
        return `.${quadrantClass} .${cellClass}`;
    }
    getTableRect() {
        return Rect.wrap(this.tableElement.getBoundingClientRect());
    }
    convertCellIndexToClientX = (index) => {
        return this.grid.getCumulativeWidthAt(index);
    };
    convertCellMidpointToClientX = (index) => {
        const cellLeft = this.grid.getCumulativeWidthBefore(index);
        const cellRight = this.grid.getCumulativeWidthAt(index);
        return (cellLeft + cellRight) / 2;
    };
    convertCellIndexToClientY = (index) => {
        return this.grid.getCumulativeHeightAt(index);
    };
    convertCellMidpointToClientY = (index) => {
        const cellTop = this.grid.getCumulativeHeightBefore(index);
        const cellBottom = this.grid.getCumulativeHeightAt(index);
        return (cellTop + cellBottom) / 2;
    };
    toGridX = (clientX) => {
        const gridOffsetFromPageLeft = this.cellContainerElement.getBoundingClientRect().left;
        const scrollOffsetFromGridLeft = this.scrollContainerElement.scrollLeft;
        const cursorOffsetFromGridLeft = clientX - (gridOffsetFromPageLeft + scrollOffsetFromGridLeft);
        const isCursorWithinFrozenColumns = this.numFrozenColumns != null &&
            this.numFrozenColumns > 0 &&
            cursorOffsetFromGridLeft <= this.grid.getCumulativeWidthBefore(this.numFrozenColumns);
        // the frozen-column region doesn't scroll, so ignore the scroll distance in that case
        return isCursorWithinFrozenColumns
            ? cursorOffsetFromGridLeft
            : cursorOffsetFromGridLeft + scrollOffsetFromGridLeft;
    };
    toGridY = (clientY) => {
        const gridOffsetFromPageTop = this.cellContainerElement.getBoundingClientRect().top;
        const scrollOffsetFromGridTop = this.scrollContainerElement.scrollTop;
        const cursorOffsetFromGridTop = clientY - (gridOffsetFromPageTop + scrollOffsetFromGridTop);
        const isCursorWithinFrozenRows = this.numFrozenRows != null &&
            this.numFrozenRows > 0 &&
            cursorOffsetFromGridTop <= this.grid.getCumulativeHeightBefore(this.numFrozenRows);
        return isCursorWithinFrozenRows ? cursorOffsetFromGridTop : cursorOffsetFromGridTop + scrollOffsetFromGridTop;
    };
}
//# sourceMappingURL=locator.js.map