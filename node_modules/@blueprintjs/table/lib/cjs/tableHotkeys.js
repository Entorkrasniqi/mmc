"use strict";
/*
 * Copyright 2021 Palantir Technologies, Inc. All rights reserved.
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.TableHotkeys = void 0;
const tslib_1 = require("tslib");
const react_1 = require("react");
const cellTypes_1 = require("./common/cellTypes");
const clipboard_1 = require("./common/clipboard");
const direction_1 = require("./common/direction");
const errors_1 = require("./common/errors");
const FocusedCellUtils = tslib_1.__importStar(require("./common/internal/focusedCellUtils"));
const SelectionUtils = tslib_1.__importStar(require("./common/internal/selectionUtils"));
const regions_1 = require("./regions");
class TableHotkeys {
    props;
    state;
    tableHandlers;
    grid;
    constructor(props, state, tableHandlers) {
        this.props = props;
        this.state = state;
        this.tableHandlers = tableHandlers;
        // no-op
    }
    setGrid(grid) {
        this.grid = grid;
    }
    setProps(props) {
        this.props = props;
    }
    setState(newState) {
        if (newState.focusedRegion != null &&
            (this.state.focusedRegion == null ||
                !FocusedCellUtils.areFocusedRegionsEqual(this.state.focusedRegion, newState.focusedRegion))) {
            this.scrollBodyToFocusedRegion(newState.focusedRegion);
        }
        this.state = newState;
    }
    // Selection
    // =========
    selectAll = (shouldUpdateFocusedCell) => {
        const selectionHandler = this.tableHandlers.getEnabledSelectionHandler(regions_1.RegionCardinality.FULL_TABLE);
        // clicking on upper left hand corner sets selection to "all"
        // regardless of current selection state (clicking twice does not deselect table)
        selectionHandler([regions_1.Regions.table()]);
        if (shouldUpdateFocusedCell) {
            const focusMode = FocusedCellUtils.getFocusModeFromProps(this.props);
            const newFocusedCellCoordinates = regions_1.Regions.getFocusCellCoordinatesFromRegion(regions_1.Regions.table());
            const newFocusedRegion = FocusedCellUtils.toFocusedRegion(focusMode, newFocusedCellCoordinates);
            if (newFocusedRegion != null) {
                this.tableHandlers.handleFocus(newFocusedRegion);
            }
        }
    };
    handleSelectAllHotkey = (e) => {
        // prevent "real" select all from happening as well
        e.preventDefault();
        e.stopPropagation();
        // selecting-all via the keyboard should not move the focused cell.
        this.selectAll(false);
    };
    handleSelectionResizeUp = (e) => this.handleSelectionResize(e, direction_1.Direction.UP);
    handleSelectionResizeDown = (e) => this.handleSelectionResize(e, direction_1.Direction.DOWN);
    handleSelectionResizeLeft = (e) => this.handleSelectionResize(e, direction_1.Direction.LEFT);
    handleSelectionResizeRight = (e) => this.handleSelectionResize(e, direction_1.Direction.RIGHT);
    handleSelectionResize = (e, direction) => {
        e.preventDefault();
        e.stopPropagation();
        const { focusedRegion, selectedRegions } = this.state;
        const index = FocusedCellUtils.getFocusedOrLastSelectedIndex(selectedRegions, focusedRegion);
        if (index === undefined) {
            return;
        }
        const region = selectedRegions[index];
        const nextRegion = SelectionUtils.resizeRegion(region, direction, focusedRegion);
        this.updateSelectedRegionAtIndex(nextRegion, index);
    };
    /**
     * Replaces the selected region at the specified array index, with the
     * region provided.
     */
    updateSelectedRegionAtIndex(region, index) {
        const { children, numRows } = this.props;
        const { selectedRegions } = this.state;
        const numColumns = react_1.Children.count(children);
        const maxRowIndex = Math.max(0, numRows - 1);
        const maxColumnIndex = Math.max(0, numColumns - 1);
        const clampedNextRegion = regions_1.Regions.clampRegion(region, maxRowIndex, maxColumnIndex);
        const nextSelectedRegions = regions_1.Regions.update(selectedRegions, clampedNextRegion, index);
        this.tableHandlers.handleSelection(nextSelectedRegions);
    }
    // Focus
    // =====
    handleFocusMoveLeft = (e) => this.handleFocusMove(e, direction_1.Direction.LEFT);
    handleFocusMoveLeftInternal = (e) => this.handleFocusMoveInternal(e, direction_1.Direction.LEFT);
    handleFocusMoveRight = (e) => this.handleFocusMove(e, direction_1.Direction.RIGHT);
    handleFocusMoveRightInternal = (e) => this.handleFocusMoveInternal(e, direction_1.Direction.RIGHT);
    handleFocusMoveUp = (e) => this.handleFocusMove(e, direction_1.Direction.UP);
    handleFocusMoveUpInternal = (e) => this.handleFocusMoveInternal(e, direction_1.Direction.UP);
    handleFocusMoveDown = (e) => this.handleFocusMove(e, direction_1.Direction.DOWN);
    handleFocusMoveDownInternal = (e) => this.handleFocusMoveInternal(e, direction_1.Direction.DOWN);
    // no good way to call arrow-key keyboard events from tests
    /* istanbul ignore next */
    handleFocusMove = (e, direction) => {
        const { focusedRegion } = this.state;
        if (focusedRegion == null) {
            // halt early if we have a selectedRegionTransform or something else in play that nixes
            // the focused cell.
            return;
        }
        const newFocusedRegion = TableHotkeys.moveFocusedRegionInDirection(focusedRegion, direction);
        if (this.isOutOfBounds(newFocusedRegion)) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        // change selection to match new focus region location
        const newSelectionRegions = [regions_1.Regions.getRegionFromFocusedRegion(newFocusedRegion)];
        const { selectedRegionTransform } = this.props;
        const transformedSelectionRegions = selectedRegionTransform != null
            ? newSelectionRegions.map(region => selectedRegionTransform(region, e))
            : newSelectionRegions;
        this.tableHandlers.handleSelection(transformedSelectionRegions);
        this.tableHandlers.handleFocus(newFocusedRegion);
        // keep the focused region in view
        this.scrollBodyToFocusedRegion(newFocusedRegion);
    };
    static moveFocusedRegionInDirection(focusedRegion, direction) {
        switch (focusedRegion.type) {
            case cellTypes_1.FocusMode.CELL:
                return TableHotkeys.moveFocusedCellInDirection(focusedRegion, direction);
            case cellTypes_1.FocusMode.ROW:
                return TableHotkeys.moveFocusedRowInDirection(focusedRegion, direction);
        }
    }
    static moveFocusedRowInDirection(focusedRow, direction) {
        switch (direction) {
            case direction_1.Direction.UP:
                return { ...focusedRow, focusSelectionIndex: 0, row: focusedRow.row - 1 };
            case direction_1.Direction.DOWN:
                return { ...focusedRow, focusSelectionIndex: 0, row: focusedRow.row + 1 };
            case direction_1.Direction.LEFT:
            case direction_1.Direction.RIGHT:
                return { ...focusedRow };
        }
    }
    static moveFocusedCellInDirection(focusedCell, direction) {
        switch (direction) {
            case direction_1.Direction.UP:
                return { ...focusedCell, focusSelectionIndex: 0, row: focusedCell.row - 1 };
            case direction_1.Direction.DOWN:
                return { ...focusedCell, focusSelectionIndex: 0, row: focusedCell.row + 1 };
            case direction_1.Direction.LEFT:
                return { ...focusedCell, col: focusedCell.col - 1, focusSelectionIndex: 0 };
            case direction_1.Direction.RIGHT:
                return { ...focusedCell, col: focusedCell.col + 1, focusSelectionIndex: 0 };
        }
    }
    // no good way to call arrow-key keyboard events from tests
    /* istanbul ignore next */
    handleFocusMoveInternal = (e, direction) => {
        const { focusedRegion, selectedRegions } = this.state;
        if (focusedRegion?.type !== cellTypes_1.FocusMode.CELL) {
            // Move focus with in a selection is only supported for cell focus
            return;
        }
        let newFocusedCell = { ...focusedRegion };
        // if we're not in any particular focus cell region, and one exists, go to the first cell of the first one
        if (focusedRegion.focusSelectionIndex == null && selectedRegions.length > 0) {
            const focusCellRegion = regions_1.Regions.getCellRegionFromRegion(selectedRegions[0], this.grid.numRows, this.grid.numCols);
            newFocusedCell = {
                col: focusCellRegion.cols[0],
                focusSelectionIndex: 0,
                row: focusCellRegion.rows[0],
                type: cellTypes_1.FocusMode.CELL,
            };
        }
        else {
            if (selectedRegions.length === 0) {
                this.handleFocusMove(e, direction);
                return;
            }
            const focusCellRegion = regions_1.Regions.getCellRegionFromRegion(selectedRegions[focusedRegion.focusSelectionIndex], this.grid.numRows, this.grid.numCols);
            if (focusCellRegion.cols[0] === focusCellRegion.cols[1] &&
                focusCellRegion.rows[0] === focusCellRegion.rows[1] &&
                selectedRegions.length === 1) {
                this.handleFocusMove(e, direction);
                return;
            }
            switch (direction) {
                case direction_1.Direction.UP:
                    newFocusedCell = this.moveFocusCell("row", "col", true, newFocusedCell, focusCellRegion);
                    break;
                case direction_1.Direction.LEFT:
                    newFocusedCell = this.moveFocusCell("col", "row", true, newFocusedCell, focusCellRegion);
                    break;
                case direction_1.Direction.DOWN:
                    newFocusedCell = this.moveFocusCell("row", "col", false, newFocusedCell, focusCellRegion);
                    break;
                case direction_1.Direction.RIGHT:
                    newFocusedCell = this.moveFocusCell("col", "row", false, newFocusedCell, focusCellRegion);
                    break;
                default:
                    break;
            }
        }
        if (this.isOutOfBounds(newFocusedCell)) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        this.tableHandlers.handleFocus(newFocusedCell);
        // keep the focused cell in view
        this.scrollBodyToFocusedRegion(newFocusedCell);
    };
    isOutOfBounds(focusedRegion) {
        const column = FocusedCellUtils.getFocusedColumn(focusedRegion) ?? 0;
        return (focusedRegion.row < 0 ||
            focusedRegion.row >= this.grid.numRows ||
            column < 0 ||
            column >= this.grid.numCols);
    }
    scrollBodyToFocusedRegion = (focusedRegion) => {
        const { row } = focusedRegion;
        const col = FocusedCellUtils.getFocusedColumn(focusedRegion);
        const { viewportRect } = this.state;
        if (viewportRect === undefined || this.grid === undefined) {
            return;
        }
        const frozenRowsHeight = this.grid.getCumulativeHeightBefore(this.state.numFrozenRowsClamped);
        const frozenColumnsWidth = this.grid.getCumulativeWidthBefore(this.state.numFrozenColumnsClamped);
        // sort keys in normal CSS position order (per the trusty TRBL/"tr ouble" acronym)
        /* eslint-disable sort-keys */
        const viewportBounds = {
            top: viewportRect.top,
            right: viewportRect.left + viewportRect.width,
            bottom: viewportRect.top + viewportRect.height,
            left: viewportRect.left,
        };
        const { columnHeaderHeight, rowHeaderWidth } = this.tableHandlers.getHeaderDimensions();
        // Bounds of the part of the viewport that contains visible, scrollable cells.
        const scrollableSectionBounds = {
            top: viewportBounds.top + columnHeaderHeight + frozenRowsHeight,
            right: viewportBounds.right,
            bottom: viewportBounds.bottom,
            left: viewportBounds.left + rowHeaderWidth + frozenColumnsWidth,
        };
        // Cumulative col widths and row heights coordinates start do _not_ include header size. ViewportRect does. Add
        // header size so that we use the same origin.
        const focusedCellBounds = {
            top: this.grid.getCumulativeHeightBefore(row) + columnHeaderHeight,
            right: this.grid.getCumulativeWidthAt(col ?? 0) + rowHeaderWidth,
            bottom: this.grid.getCumulativeHeightAt(row) + columnHeaderHeight,
            left: this.grid.getCumulativeWidthBefore(col ?? 0) + rowHeaderWidth,
        };
        /* eslint-enable sort-keys */
        const ss = {};
        // Vertical scroll
        const focusedCellHeight = focusedCellBounds.bottom - focusedCellBounds.top;
        const scrollableSectionHeight = scrollableSectionBounds.bottom - scrollableSectionBounds.top;
        const prevScrollTop = viewportBounds.top;
        if (focusedCellHeight > scrollableSectionHeight || focusedCellBounds.top < scrollableSectionBounds.top) {
            // scroll up (minus one pixel to avoid clipping the focused-cell border)
            ss.nextScrollTop = prevScrollTop - (scrollableSectionBounds.top - focusedCellBounds.top) - 1;
        }
        else if (scrollableSectionBounds.bottom < focusedCellBounds.bottom) {
            // scroll down
            ss.nextScrollTop = prevScrollTop + (focusedCellBounds.bottom - viewportBounds.bottom);
        }
        // Horizontal scroll
        if (col != null) {
            const focusedCellWidth = focusedCellBounds.right - focusedCellBounds.left;
            const scrollableSectionWidth = scrollableSectionBounds.right - scrollableSectionBounds.left;
            const prevScrollLeft = viewportBounds.left;
            if (focusedCellWidth > scrollableSectionWidth || focusedCellBounds.left < scrollableSectionBounds.left) {
                // scroll left (again minus one additional pixel)
                ss.nextScrollLeft = prevScrollLeft - (scrollableSectionBounds.left - focusedCellBounds.left) - 1;
            }
            else if (scrollableSectionBounds.right < focusedCellBounds.right) {
                // scroll right
                ss.nextScrollLeft = prevScrollLeft + (focusedCellBounds.right - viewportBounds.right);
            }
        }
        this.tableHandlers.syncViewportPosition(ss);
    };
    // Quadrant refs
    // =============
    moveFocusCell(primaryAxis, secondaryAxis, isUpOrLeft, newFocusedCell, focusCellRegion) {
        const { selectedRegions } = this.state;
        const primaryAxisPlural = primaryAxis === "row" ? "rows" : "cols";
        const secondaryAxisPlural = secondaryAxis === "row" ? "rows" : "cols";
        const movementDirection = isUpOrLeft ? -1 : +1;
        const regionIntervalIndex = isUpOrLeft ? 1 : 0;
        // try moving the cell in the direction along the primary axis
        newFocusedCell[primaryAxis] += movementDirection;
        const isPrimaryIndexOutOfBounds = isUpOrLeft
            ? newFocusedCell[primaryAxis] < focusCellRegion[primaryAxisPlural][0]
            : newFocusedCell[primaryAxis] > focusCellRegion[primaryAxisPlural][1];
        if (isPrimaryIndexOutOfBounds) {
            // if we moved outside the bounds of selection region,
            // move to the start (or end) of the primary axis, and move one along the secondary
            newFocusedCell[primaryAxis] = focusCellRegion[primaryAxisPlural][regionIntervalIndex];
            newFocusedCell[secondaryAxis] += movementDirection;
            const isSecondaryIndexOutOfBounds = isUpOrLeft
                ? newFocusedCell[secondaryAxis] < focusCellRegion[secondaryAxisPlural][0]
                : newFocusedCell[secondaryAxis] > focusCellRegion[secondaryAxisPlural][1];
            if (isSecondaryIndexOutOfBounds) {
                // if moving along the secondary also moves us outside
                // go to the start (or end) of the next (or previous region)
                // (note that if there's only one region you'll be moving to the opposite corner, which is fine)
                let newFocusCellSelectionIndex = newFocusedCell.focusSelectionIndex + movementDirection;
                // newFocusCellSelectionIndex should be one more (or less), unless we need to wrap around
                if (isUpOrLeft ? newFocusCellSelectionIndex < 0 : newFocusCellSelectionIndex >= selectedRegions.length) {
                    newFocusCellSelectionIndex = isUpOrLeft ? selectedRegions.length - 1 : 0;
                }
                const newFocusCellRegion = regions_1.Regions.getCellRegionFromRegion(selectedRegions[newFocusCellSelectionIndex], this.grid.numRows, this.grid.numCols);
                newFocusedCell = {
                    col: newFocusCellRegion.cols[regionIntervalIndex],
                    focusSelectionIndex: newFocusCellSelectionIndex,
                    row: newFocusCellRegion.rows[regionIntervalIndex],
                    type: cellTypes_1.FocusMode.CELL,
                };
            }
        }
        return newFocusedCell;
    }
    handleCopy = (e) => {
        const { getCellClipboardData, onCopy } = this.props;
        const { selectedRegions } = this.state;
        if (getCellClipboardData == null || this.grid === undefined || window.getSelection()?.toString()) {
            return;
        }
        // prevent "real" copy from being called
        e.preventDefault();
        e.stopPropagation();
        const cells = regions_1.Regions.enumerateUniqueCells(selectedRegions, this.grid.numRows, this.grid.numCols);
        // non-null assertion because Column.defaultProps.cellRenderer is defined
        const sparse = regions_1.Regions.sparseMapCells(cells, (row, col) => getCellClipboardData(row, col, this.state.childrenArray[col].props.cellRenderer));
        if (sparse != null) {
            clipboard_1.Clipboard.copyCells(sparse)
                .then(() => onCopy?.(true))
                .catch((reason) => {
                console.error(errors_1.TABLE_COPY_FAILED, reason);
                onCopy?.(false);
            });
        }
    };
}
exports.TableHotkeys = TableHotkeys;
//# sourceMappingURL=tableHotkeys.js.map