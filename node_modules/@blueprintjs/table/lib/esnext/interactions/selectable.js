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
import { PureComponent } from "react";
import { Utils as CoreUtils, DISPLAYNAME_PREFIX } from "@blueprintjs/core";
import { FocusMode } from "../common/cellTypes";
import * as DefaultFocusedCellUtils from "../common/internal/focusedCellUtils";
import * as PlatformUtils from "../common/internal/platformUtils";
import { Utils } from "../common/utils";
import { Regions } from "../regions";
import { DragEvents } from "./dragEvents";
import { Draggable } from "./draggable";
export class DragSelectable extends PureComponent {
    static defaultProps = {
        disabled: false,
        enableMultipleSelection: false,
        selectedRegions: [],
    };
    static displayName = `${DISPLAYNAME_PREFIX}.DragSelectable`;
    get focusedCellUtils() {
        return {
            ...DefaultFocusedCellUtils,
            ...this.props.focusedCellUtils,
        };
    }
    didExpandSelectionOnActivate = false;
    lastEmittedSelectedRegions = null;
    render() {
        const draggableProps = this.getDraggableHandlers();
        return (_jsx(Draggable, { ...draggableProps, preventDefault: false, targetRef: this.props.targetRef, children: this.props.children }));
    }
    getDraggableHandlers() {
        return this.props.onSelection == null
            ? {}
            : {
                onActivate: this.handleActivate,
                onClick: this.handleClick,
                onDragEnd: this.handleDragEnd,
                onDragMove: this.handleDragMove,
            };
    }
    handleActivate = (event) => {
        const { locateClick, selectedRegions, selectedRegionTransform } = this.props;
        if (this.shouldIgnoreMouseDown(event)) {
            return false;
        }
        let region = locateClick(event);
        if (!Regions.isValid(region)) {
            return false;
        }
        if (selectedRegionTransform != null) {
            region = selectedRegionTransform(region, event);
        }
        const foundIndex = Regions.findMatchingRegion(selectedRegions, region);
        const matchesExistingSelection = foundIndex !== -1;
        if (matchesExistingSelection && DragEvents.isAdditive(event)) {
            this.handleClearSelectionAtIndex(foundIndex);
            // if we just deselected a selected region, a subsequent drag-move
            // could reselect it again and *also* clear other selections. that's
            // quite unintuitive, so ignore subsequent drag-move's.
            return false;
        }
        // we want to listen to subsequent drag-move's in all following cases,
        // so this mousedown can be the start of a new selection if desired.
        if (matchesExistingSelection) {
            this.handleClearAllSelectionsNotAtIndex(foundIndex);
        }
        else if (this.shouldExpandSelection(event)) {
            this.handleExpandSelection(region);
        }
        else if (this.shouldAddDisjointSelection(event)) {
            this.handleAddDisjointSelection(region);
        }
        else {
            this.handleReplaceSelection(region);
        }
        return true;
    };
    handleDragMove = (event, coords) => {
        const { enableMultipleSelection, locateClick, locateDrag, selectedRegions, selectedRegionTransform } = this.props;
        let region = enableMultipleSelection
            ? locateDrag(event, coords, /* returnEndOnly? */ this.didExpandSelectionOnActivate)
            : locateClick(event);
        if (region === undefined || !Regions.isValid(region)) {
            return;
        }
        else if (selectedRegionTransform != null) {
            region = selectedRegionTransform(region, event, coords);
        }
        const nextSelectedRegions = this.didExpandSelectionOnActivate
            ? this.expandSelectedRegions(selectedRegions, region, this.getFocusedRegion())
            : Regions.update(selectedRegions, region);
        this.maybeInvokeSelectionCallback(nextSelectedRegions);
        if (!enableMultipleSelection) {
            // move the focused cell with the selected region
            const lastIndex = nextSelectedRegions.length - 1;
            const mostRecentRegion = nextSelectedRegions[lastIndex];
            this.invokeOnFocusCallbackForRegion(mostRecentRegion, lastIndex);
        }
    };
    handleDragEnd = () => {
        this.finishInteraction();
    };
    handleClick = () => {
        this.finishInteraction();
    };
    // Boolean checks
    // ==============
    shouldExpandSelection = (event) => {
        const { enableMultipleSelection } = this.props;
        return enableMultipleSelection && event.shiftKey;
    };
    shouldAddDisjointSelection = (event) => {
        const { enableMultipleSelection } = this.props;
        return enableMultipleSelection && DragEvents.isAdditive(event);
    };
    shouldIgnoreMouseDown(event) {
        const { disabled, ignoredSelectors = [] } = this.props;
        const element = event.target;
        const isLeftClick = Utils.isLeftClick(event);
        const isContextMenuTrigger = isLeftClick && event.ctrlKey && PlatformUtils.isMac();
        const isDisabled = typeof disabled === "function" ? disabled(event) : disabled;
        return (!isLeftClick ||
            isContextMenuTrigger ||
            isDisabled ||
            ignoredSelectors.some((selector) => element.closest(selector) != null));
    }
    // Update logic
    // ============
    handleClearSelectionAtIndex = (selectedRegionIndex) => {
        const { selectedRegions } = this.props;
        // remove just the clicked region, leaving other selected regions in place
        const nextSelectedRegions = selectedRegions.slice();
        nextSelectedRegions.splice(selectedRegionIndex, 1);
        this.maybeInvokeSelectionCallback(nextSelectedRegions);
        // if there are still any selections, move the focused cell to the
        // most recent selection. otherwise, don't update it.
        if (nextSelectedRegions.length > 0) {
            const lastIndex = nextSelectedRegions.length - 1;
            this.invokeOnFocusCallbackForRegion(nextSelectedRegions[lastIndex], lastIndex);
        }
    };
    handleClearAllSelectionsNotAtIndex = (selectedRegionIndex) => {
        const { selectedRegions } = this.props;
        const nextSelectedRegion = selectedRegions[selectedRegionIndex];
        this.maybeInvokeSelectionCallback([nextSelectedRegion]);
        this.invokeOnFocusCallbackForRegion(nextSelectedRegion, 0);
    };
    handleExpandSelection = (region) => {
        const { selectedRegions } = this.props;
        this.didExpandSelectionOnActivate = true;
        // there should be only one selected region after expanding. do not
        // update the focused cell.
        const nextSelectedRegions = this.expandSelectedRegions(selectedRegions, region, this.getFocusedRegion());
        this.maybeInvokeSelectionCallback(nextSelectedRegions);
        // move the focused cell into the new region if there were no selections before
        if (selectedRegions == null || selectedRegions.length === 0) {
            this.invokeOnFocusCallbackForRegion(region);
        }
    };
    handleAddDisjointSelection = (region) => {
        const { selectedRegions } = this.props;
        // add the new region to the existing selections
        const nextSelectedRegions = Regions.add(selectedRegions, region);
        this.maybeInvokeSelectionCallback(nextSelectedRegions);
        // put the focused cell in the new region
        this.invokeOnFocusCallbackForRegion(region, nextSelectedRegions.length - 1);
    };
    handleReplaceSelection = (region) => {
        // clear all selections and retain only the new one
        const nextSelectedRegions = [region];
        this.maybeInvokeSelectionCallback(nextSelectedRegions);
        // move the focused cell into the new selection
        this.invokeOnFocusCallbackForRegion(region);
    };
    // Callbacks
    // =========
    maybeInvokeSelectionCallback(nextSelectedRegions) {
        const { onSelection } = this.props;
        // invoke only if the selection changed. this is useful only on
        // mousemove; there's special handling for mousedown interactions that
        // target an already-selected region.
        if (this.lastEmittedSelectedRegions == null ||
            !CoreUtils.deepCompareKeys(this.lastEmittedSelectedRegions, nextSelectedRegions)) {
            onSelection(nextSelectedRegions);
            this.lastEmittedSelectedRegions = nextSelectedRegions;
        }
    }
    invokeOnFocusCallbackForRegion = (focusRegion, focusSelectionIndex = 0) => {
        // eslint-disable-next-line @typescript-eslint/no-deprecated
        const { focusMode, onFocusedCell, onFocusedRegion } = this.props;
        const focusedCellCoords = Regions.getFocusCellCoordinatesFromRegion(focusRegion);
        const newFocusedRegion = this.focusedCellUtils.toFocusedRegion(focusMode, focusedCellCoords, focusSelectionIndex);
        if (newFocusedRegion != null) {
            onFocusedRegion?.(newFocusedRegion);
        }
        // Keep this call for backward compatibility
        onFocusedCell?.(this.focusedCellUtils.toFocusedRegion(FocusMode.CELL, focusedCellCoords, focusSelectionIndex));
    };
    // Other
    // =====
    finishInteraction = () => {
        this.props.onSelectionEnd?.(this.props.selectedRegions);
        this.didExpandSelectionOnActivate = false;
        this.lastEmittedSelectedRegions = null;
    };
    /**
     * Expands the last-selected region to the new region, and replaces the
     * last-selected region with the expanded region. If a focused cell is provided,
     * the focused cell will serve as an anchor for the expansion.
     */
    expandSelectedRegions(regions, region, focusedRegion) {
        if (regions.length === 0) {
            return [region];
        }
        else if (focusedRegion != null) {
            const expandedRegion = this.focusedCellUtils.expandFocusedRegion(focusedRegion, region);
            return Regions.update(regions, expandedRegion);
        }
        else {
            const expandedRegion = Regions.expandRegion(regions[regions.length - 1], region);
            return Regions.update(regions, expandedRegion);
        }
    }
    getFocusedRegion() {
        // eslint-disable-next-line @typescript-eslint/no-deprecated
        const { focusedCell, focusedRegion } = this.props;
        if (focusedRegion != null) {
            return focusedRegion;
        }
        if (focusedCell != null) {
            return { ...focusedCell, type: FocusMode.CELL };
        }
        return undefined;
    }
}
//# sourceMappingURL=selectable.js.map