"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.getFocusModeFromProps = getFocusModeFromProps;
exports.getFocusedRegionFromProps = getFocusedRegionFromProps;
exports.getFocusedCellFromCoordinates = getFocusedCellFromCoordinates;
exports.getFocusedOrLastSelectedIndex = getFocusedOrLastSelectedIndex;
exports.getInitialFocusedRegion = getInitialFocusedRegion;
exports.validateFocusedRegion = validateFocusedRegion;
exports.isFocusAtRegionTop = isFocusAtRegionTop;
exports.isFocusAtRegionBottom = isFocusAtRegionBottom;
exports.isFocusAtRegionLeft = isFocusAtRegionLeft;
exports.isFocusAtRegionRight = isFocusAtRegionRight;
exports.getFocusedColumn = getFocusedColumn;
exports.toFocusedRegion = toFocusedRegion;
exports.expandFocusedRegion = expandFocusedRegion;
exports.areFocusedRegionsEqual = areFocusedRegionsEqual;
const tslib_1 = require("tslib");
const regions_1 = require("../../regions");
const cellTypes_1 = require("../cellTypes");
const Errors = tslib_1.__importStar(require("../errors"));
/**
 * Returns the inferred focus mode from the table props. This prefers the new focus mode API, falling back to the
 * deprecated enableFocusedCell API if that is not provided.
 */
function getFocusModeFromProps(props) {
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    const { enableFocusedCell, focusMode } = props;
    return focusMode ?? getFocusModeFromEnabled(enableFocusedCell);
}
function getFocusModeFromEnabled(enableFocusedCell = false) {
    return enableFocusedCell ? cellTypes_1.FocusMode.CELL : undefined;
}
/**
 * Returns the inferred focused region from the table props. This prefers the new focus mode API, falling back to the
 * deprecated API if a focused region is not provided.
 */
function getFocusedRegionFromProps(props) {
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    const { focusedRegion, focusedCell } = props;
    return focusedRegion ?? getFocusedCellFromCoordinates(focusedCell);
}
function getFocusedCellFromCoordinates(focusedCell) {
    return focusedCell != null ? { type: cellTypes_1.FocusMode.CELL, ...focusedCell } : undefined;
}
/**
 * Returns the `focusedSelectionIndex` if both the focused region and that
 * property are defined, or the last index of `selectedRegions` otherwise. If
 * `selectedRegions` is empty, the function always returns `undefined`.
 */
function getFocusedOrLastSelectedIndex(selectedRegions, focusedRegion) {
    if (selectedRegions.length === 0) {
        return undefined;
    }
    else if (focusedRegion != null) {
        return focusedRegion.focusSelectionIndex;
    }
    else {
        return selectedRegions.length - 1;
    }
}
/**
 * Returns the proper focused region for the given set of initial conditions.
 */
function getInitialFocusedRegion(focusMode, focusedRegionFromProps, focusedRegionFromState, selectedRegions) {
    return validateFocusedRegion(focusMode, getInitialFocusedCell(focusedRegionFromProps, focusedRegionFromState, selectedRegions));
}
function getInitialFocusedCell(focusedRegionFromProps, focusedRegionFromState, selectedRegions) {
    return focusedRegionFromProps ?? focusedRegionFromState ?? getInitialFocusedCellFromSelection(selectedRegions);
}
function getInitialFocusedCellFromSelection(selectedRegions) {
    if (selectedRegions.length === 0) {
        return { col: 0, focusSelectionIndex: 0, row: 0, type: cellTypes_1.FocusMode.CELL };
    }
    const lastIndex = selectedRegions.length - 1;
    // focus the top-left cell of the last selection
    return {
        ...regions_1.Regions.getFocusCellCoordinatesFromRegion(selectedRegions[lastIndex]),
        focusSelectionIndex: lastIndex,
        type: cellTypes_1.FocusMode.CELL,
    };
}
/**
 * Returns a focused region that matches the given focus mode if possible. If such a conversion is not possible,
 * returns undefined instead.
 */
function validateFocusedRegion(focusMode, focusedRegion) {
    if (focusMode == null) {
        return undefined;
    }
    if (focusedRegion.type === focusMode) {
        return focusedRegion;
    }
    if (focusedRegion.type === cellTypes_1.FocusMode.CELL && focusMode === cellTypes_1.FocusMode.ROW) {
        return {
            focusSelectionIndex: focusedRegion.focusSelectionIndex,
            row: focusedRegion.row,
            type: focusMode,
        };
    }
    if (focusedRegion.type === cellTypes_1.FocusMode.ROW && focusMode === cellTypes_1.FocusMode.CELL) {
        return {
            col: 0,
            focusSelectionIndex: focusedRegion.focusSelectionIndex,
            row: focusedRegion.row,
            type: focusMode,
        };
    }
    return undefined;
}
/**
 * Returns `true` if the focused region is located along the top boundary of the
 * provided region, or `false` otherwise.
 */
function isFocusAtRegionTop(region, focusedRegion) {
    return region.rows != null && focusedRegion.row === region.rows[0];
}
/**
 * Returns `true` if the focused region is located along the bottom boundary of
 * the provided region, or `false` otherwise.
 */
function isFocusAtRegionBottom(region, focusedRegion) {
    return region.rows != null && focusedRegion.row === region.rows[1];
}
/**
 * Returns `true` if the focused region is located along the left boundary of the
 * provided region, or `false` otherwise.
 */
function isFocusAtRegionLeft(region, focusedRegion) {
    return region.cols != null && getFocusedColumn(focusedRegion) === region.cols[0];
}
/**
 * Returns `true` if the focused region is located along the right boundary of the
 * provided region, or `false` otherwise.
 */
function isFocusAtRegionRight(region, focusedRegion) {
    return region.cols != null && getFocusedColumn(focusedRegion) === region.cols[1];
}
/**
 * Returns the column associated with this region, if there is one.
 */
function getFocusedColumn(focusedRegion) {
    switch (focusedRegion.type) {
        case cellTypes_1.FocusMode.CELL:
            return focusedRegion.col;
        case cellTypes_1.FocusMode.ROW:
            return undefined;
    }
}
function toFocusedRegion(focusMode, cellCoords, focusSelectionIndex = 0) {
    switch (focusMode) {
        case cellTypes_1.FocusMode.CELL:
            return { type: cellTypes_1.FocusMode.CELL, ...cellCoords, focusSelectionIndex };
        case cellTypes_1.FocusMode.ROW:
            return { focusSelectionIndex, row: cellCoords.row, type: cellTypes_1.FocusMode.ROW };
        case undefined:
            return undefined;
    }
}
/**
 * Expands an existing region to new region based on the current focused region.
 * The focused region is an invariant and should not move as a result of this
 * operation. This function is used, for instance, to expand a selected region
 * on shift+click.
 */
function expandFocusedRegion(focusedRegion, newRegion) {
    switch (regions_1.Regions.getRegionCardinality(newRegion)) {
        case regions_1.RegionCardinality.FULL_COLUMNS: {
            const [indexStart, indexEnd] = getExpandedRegionIndices(focusedRegion, newRegion, "col", "cols");
            return regions_1.Regions.column(indexStart, indexEnd);
        }
        case regions_1.RegionCardinality.FULL_ROWS: {
            const [indexStart, indexEnd] = getExpandedRegionIndices(focusedRegion, newRegion, "row", "rows");
            return regions_1.Regions.row(indexStart, indexEnd);
        }
        case regions_1.RegionCardinality.CELLS:
            const [rowIndexStart, rowIndexEnd] = getExpandedRegionIndices(focusedRegion, newRegion, "row", "rows");
            const [colIndexStart, colIndexEnd] = getExpandedRegionIndices(focusedRegion, newRegion, "col", "cols");
            return regions_1.Regions.cell(rowIndexStart, colIndexStart, rowIndexEnd, colIndexEnd);
        default:
            // i.e. `case RegionCardinality.FULL_TABLE:`
            return regions_1.Regions.table();
    }
}
function getExpandedRegionIndices(focusedRegion, newRegion, focusedCellDimension, regionDimension) {
    const sourceIndex = focusedCellDimension === "row" ? focusedRegion.row : (getFocusedColumn(focusedRegion) ?? 0); // THIS IS QUESTIONABLE AT BEST
    const [destinationIndex, destinationIndexEnd] = newRegion[regionDimension];
    if (destinationIndex !== destinationIndexEnd) {
        if (regionDimension === "rows") {
            throw new Error(Errors.TABLE_EXPAND_FOCUSED_REGION_MULTI_ROW_REGION);
        }
        else if (regionDimension === "cols") {
            throw new Error(Errors.TABLE_EXPAND_FOCUSED_REGION_MULTI_COLUMN_REGION);
        }
    }
    return sourceIndex <= destinationIndex ? [sourceIndex, destinationIndex] : [destinationIndex, sourceIndex];
}
function areFocusedRegionsEqual(left, right) {
    if (left.type === cellTypes_1.FocusMode.CELL && right.type === cellTypes_1.FocusMode.CELL) {
        return left.row === right.row && left.col === right.col;
    }
    else if (left.type === cellTypes_1.FocusMode.ROW && right.type === cellTypes_1.FocusMode.ROW) {
        return left.row === right.row;
    }
    else {
        return false;
    }
}
//# sourceMappingURL=focusedCellUtils.js.map