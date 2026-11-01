"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TableBody = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2022 Palantir Technologies, Inc. All rights reserved.
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
const Classes = tslib_1.__importStar(require("./common/classes"));
const focusedCellUtils_1 = require("./common/internal/focusedCellUtils");
const renderMode_1 = require("./common/renderMode");
const menus_1 = require("./interactions/menus");
const selectable_1 = require("./interactions/selectable");
const regions_1 = require("./regions");
const tableBodyCells_1 = require("./tableBodyCells");
const DEEP_COMPARE_KEYS = ["selectedRegions"];
class TableBody extends core_1.AbstractComponent {
    static defaultProps = {
        loading: false,
        renderMode: renderMode_1.RenderMode.BATCH,
    };
    activationCell = null;
    containerRef = (0, react_1.createRef)();
    shouldComponentUpdate(nextProps) {
        return (!core_1.Utils.shallowCompareKeys(this.props, nextProps, { exclude: DEEP_COMPARE_KEYS }) ||
            !core_1.Utils.deepCompareKeys(this.props, nextProps, DEEP_COMPARE_KEYS));
    }
    render() {
        const { grid, numFrozenColumns, numFrozenRows } = this.props;
        const defaultStyle = grid.getRect().sizeStyle();
        const style = {
            height: numFrozenRows != null ? grid.getCumulativeHeightAt(numFrozenRows - 1) : defaultStyle.height,
            width: numFrozenColumns != null ? grid.getCumulativeWidthAt(numFrozenColumns - 1) : defaultStyle.width,
        };
        return ((0, jsx_runtime_1.jsx)(selectable_1.DragSelectable, { enableMultipleSelection: this.props.enableMultipleSelection, focusedRegion: this.props.focusedRegion, focusMode: this.props.focusMode, locateClick: this.locateClick, locateDrag: this.locateDrag, onFocusedRegion: this.props.onFocusedRegion, onSelection: this.props.onSelection, onSelectionEnd: this.handleSelectionEnd, selectedRegions: this.props.selectedRegions, selectedRegionTransform: this.props.selectedRegionTransform, targetRef: this.containerRef, children: (0, jsx_runtime_1.jsx)(core_1.ContextMenu, { className: (0, classnames_1.default)(Classes.TABLE_BODY_VIRTUAL_CLIENT, Classes.TABLE_CELL_CLIENT), content: this.renderContextMenu, disabled: this.props.bodyContextMenuRenderer === undefined, onContextMenu: this.handleContextMenu, ref: this.containerRef, style: style, children: (0, jsx_runtime_1.jsx)(tableBodyCells_1.TableBodyCells, { cellRenderer: this.props.cellRenderer, focusedRegion: this.props.focusedRegion, grid: grid, loading: this.props.loading, onCompleteRender: this.props.onCompleteRender, renderMode: this.props.renderMode, columnIndexStart: this.props.columnIndexStart, columnIndexEnd: this.props.columnIndexEnd, rowIndexStart: this.props.rowIndexStart, rowIndexEnd: this.props.rowIndexEnd, viewportRect: this.props.viewportRect }) }) }));
    }
    renderContextMenu = ({ mouseEvent }) => {
        const { grid, bodyContextMenuRenderer, selectedRegions = [] } = this.props;
        const { numRows, numCols } = grid;
        if (bodyContextMenuRenderer === undefined || mouseEvent === undefined) {
            return undefined;
        }
        // Check if the event originated from inside a popover - in that case we should not show the context menu
        const eventTarget = mouseEvent.target;
        const isInsidePopover = eventTarget.closest(`.${Classes.TABLE_TRUNCATED_POPOVER}`) !== null;
        if (isInsidePopover) {
            return undefined;
        }
        const targetRegion = this.locateClick(mouseEvent.nativeEvent);
        let nextSelectedRegions = selectedRegions;
        // if the event did not happen within a selected region, clear all
        // selections and select the right-clicked cell.
        const foundIndex = regions_1.Regions.findContainingRegion(selectedRegions, targetRegion);
        if (foundIndex < 0) {
            nextSelectedRegions = [targetRegion];
        }
        const menuContext = new menus_1.MenuContextImpl(targetRegion, nextSelectedRegions, numRows, numCols);
        const contextMenu = bodyContextMenuRenderer(menuContext);
        return contextMenu == null ? undefined : contextMenu;
    };
    // Callbacks
    // =========
    // state updates cannot happen in renderContextMenu() during the render phase, so we must handle them separately
    handleContextMenu = (e) => {
        const { focusMode, onFocusedRegion, onSelection, selectedRegions = [] } = this.props;
        // Check if the event originated from inside a popover - in that case we should not handle the context menu
        const eventTarget = e.target;
        const isInsidePopover = eventTarget.closest(`.${Classes.TABLE_TRUNCATED_POPOVER}`) !== null;
        if (isInsidePopover) {
            return;
        }
        const targetRegion = this.locateClick(e.nativeEvent);
        let nextSelectedRegions = selectedRegions;
        // if the event did not happen within a selected region, clear all
        // selections and select the right-clicked cell.
        const foundIndex = regions_1.Regions.findContainingRegion(selectedRegions, targetRegion);
        if (foundIndex < 0) {
            nextSelectedRegions = [targetRegion];
            onSelection(nextSelectedRegions);
            // move the focused cell to the new region.
            const focusedCellCoords = regions_1.Regions.getFocusCellCoordinatesFromRegion(targetRegion);
            const newFocusedRegion = (0, focusedCellUtils_1.toFocusedRegion)(focusMode, focusedCellCoords);
            if (newFocusedRegion != null) {
                onFocusedRegion(newFocusedRegion);
            }
        }
    };
    handleSelectionEnd = () => {
        this.activationCell = null; // not strictly required, but good practice
    };
    locateClick = (event) => {
        this.activationCell = this.props.locator.convertPointToCell(event.clientX, event.clientY);
        return regions_1.Regions.cell(this.activationCell.row, this.activationCell.col);
    };
    locateDrag = (_event, coords, returnEndOnly = false) => {
        if (this.activationCell === null) {
            return undefined;
        }
        const start = this.activationCell;
        const end = this.props.locator.convertPointToCell(coords.current[0], coords.current[1]);
        return returnEndOnly ? regions_1.Regions.cell(end.row, end.col) : regions_1.Regions.cell(start.row, start.col, end.row, end.col);
    };
}
exports.TableBody = TableBody;
//# sourceMappingURL=tableBody.js.map