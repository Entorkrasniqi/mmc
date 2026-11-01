"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DragReorderable = void 0;
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
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const focusedCellUtils_1 = require("../common/internal/focusedCellUtils");
const utils_1 = require("../common/utils");
const regions_1 = require("../regions");
const draggable_1 = require("./draggable");
class DragReorderable extends react_1.PureComponent {
    static defaultProps = {
        selectedRegions: [],
    };
    selectedRegionStartIndex;
    selectedRegionLength = 0;
    render() {
        const draggableProps = this.getDraggableHandlers();
        return ((0, jsx_runtime_1.jsx)(draggable_1.Draggable, { ...draggableProps, preventDefault: false, targetRef: this.props.targetRef, children: this.props.children }));
    }
    getDraggableHandlers() {
        return this.props.onReordered == null
            ? {}
            : {
                onActivate: this.handleActivate,
                onDragEnd: this.handleDragEnd,
                onDragMove: this.handleDragMove,
            };
    }
    handleActivate = (event) => {
        if (this.shouldIgnoreMouseDown(event)) {
            return false;
        }
        const region = this.props.locateClick(event);
        if (!regions_1.Regions.isValid(region)) {
            return false;
        }
        const cardinality = regions_1.Regions.getRegionCardinality(region);
        const isColumnHeader = cardinality === regions_1.RegionCardinality.FULL_COLUMNS;
        const isRowHeader = cardinality === regions_1.RegionCardinality.FULL_ROWS;
        if (!isColumnHeader && !isRowHeader) {
            return false;
        }
        const { selectedRegions = [] } = this.props;
        const selectedRegionIndex = regions_1.Regions.findContainingRegion(selectedRegions, region);
        if (selectedRegionIndex >= 0) {
            const selectedRegion = selectedRegions[selectedRegionIndex];
            if (regions_1.Regions.getRegionCardinality(selectedRegion) !== cardinality) {
                // ignore FULL_TABLE selections
                return false;
            }
            // cache for easy access later in the lifecycle
            const selectedInterval = isRowHeader ? selectedRegion.rows : selectedRegion.cols;
            this.selectedRegionStartIndex = selectedInterval[0];
            // add 1 because the selected interval is inclusive, which simple subtraction doesn't
            // account for (e.g. in a FULL_COLUMNS range from 3 to 6, 6 - 3 = 3, but the selection
            // actually includes four columns: 3, 4, 5, and 6)
            this.selectedRegionLength = selectedInterval[1] - selectedInterval[0] + 1;
        }
        else {
            // select the new region to avoid complex and unintuitive UX w/r/t the existing selection
            this.maybeSelectRegion(region);
            const regionRange = isRowHeader ? region.rows : region.cols;
            this.selectedRegionStartIndex = regionRange[0];
            this.selectedRegionLength = regionRange[1] - regionRange[0] + 1;
        }
        return true;
    };
    handleDragMove = (event, coords) => {
        const oldIndex = this.selectedRegionStartIndex;
        const guideIndex = this.props.locateDrag(event, coords);
        if (oldIndex === undefined || guideIndex === undefined) {
            return;
        }
        const length = this.selectedRegionLength;
        const reorderedIndex = utils_1.Utils.guideIndexToReorderedIndex(oldIndex, guideIndex, length);
        this.props.onReordering(oldIndex, reorderedIndex, length);
    };
    handleDragEnd = (event, coords) => {
        const oldIndex = this.selectedRegionStartIndex;
        const guideIndex = this.props.locateDrag(event, coords);
        if (oldIndex === undefined || guideIndex === undefined) {
            return;
        }
        const length = this.selectedRegionLength;
        const reorderedIndex = utils_1.Utils.guideIndexToReorderedIndex(oldIndex, guideIndex, length);
        this.props.onReordered(oldIndex, reorderedIndex, length);
        // the newly reordered region becomes the only selection
        const newRegion = this.props.toRegion(reorderedIndex, reorderedIndex + length - 1);
        this.maybeSelectRegion(newRegion);
        // resetting is not strictly required, but it's cleaner
        this.selectedRegionStartIndex = undefined;
        this.selectedRegionLength = 0;
    };
    shouldIgnoreMouseDown(event) {
        const { disabled } = this.props;
        const isDisabled = core_1.Utils.isFunction(disabled) ? disabled?.(event) : disabled;
        return !utils_1.Utils.isLeftClick(event) || isDisabled;
    }
    maybeSelectRegion(region) {
        const nextSelectedRegions = [region];
        if (!core_1.Utils.deepCompareKeys(nextSelectedRegions, this.props.selectedRegions)) {
            this.props.onSelection(nextSelectedRegions);
            // move the focused cell into the newly selected region
            const focusedCellCoords = regions_1.Regions.getFocusCellCoordinatesFromRegion(region);
            const newFocusedRegion = (0, focusedCellUtils_1.toFocusedRegion)(this.props.focusMode, focusedCellCoords);
            if (newFocusedRegion != null) {
                this.props.onFocusedRegion(newFocusedRegion);
            }
        }
    }
}
exports.DragReorderable = DragReorderable;
//# sourceMappingURL=reorderable.js.map