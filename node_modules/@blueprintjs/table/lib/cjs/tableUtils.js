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
exports.clampNumFrozenColumns = clampNumFrozenColumns;
exports.clampNumFrozenRows = clampNumFrozenRows;
exports.hasLoadingOption = hasLoadingOption;
exports.isSelectionModeEnabled = isSelectionModeEnabled;
exports.getHotkeysFromProps = getHotkeysFromProps;
exports.compareChildren = compareChildren;
const react_1 = require("react");
const cellTypes_1 = require("./common/cellTypes");
const focusedCellUtils_1 = require("./common/internal/focusedCellUtils");
const utils_1 = require("./common/utils");
const regions_1 = require("./regions");
function clampNumFrozenColumns(props) {
    const { numFrozenColumns } = props;
    const numColumns = react_1.Children.count(props.children);
    return maybeClampValue(numFrozenColumns, numColumns);
}
function clampNumFrozenRows(props) {
    const { numFrozenRows, numRows } = props;
    return maybeClampValue(numFrozenRows, numRows);
}
function maybeClampValue(value, max) {
    return value === undefined ? 0 : utils_1.Utils.clamp(value, 0, max);
}
function hasLoadingOption(loadingOptions, loadingOption) {
    if (loadingOptions === undefined) {
        return false;
    }
    return loadingOptions.indexOf(loadingOption) >= 0;
}
function isSelectionModeEnabled(props, selectionMode, selectionModes = props.selectionModes) {
    const { children, numRows } = props;
    const numColumns = react_1.Children.count(children);
    return selectionModes.indexOf(selectionMode) >= 0 && numRows > 0 && numColumns > 0;
}
function getHotkeysFromProps(props, hotkeysImpl) {
    const { getCellClipboardData, enableMultipleSelection, selectionModes } = props;
    const focusMode = (0, focusedCellUtils_1.getFocusModeFromProps)(props);
    const hotkeys = [];
    if (getCellClipboardData != null) {
        hotkeys.push({
            combo: "mod+c",
            group: "Table",
            label: "Copy selected table cells",
            onKeyDown: hotkeysImpl.handleCopy,
        });
    }
    const isSomeSelectionModeEnabled = selectionModes.length > 0;
    if (enableMultipleSelection && isSomeSelectionModeEnabled) {
        hotkeys.push({
            combo: "shift+up",
            group: "Table",
            label: "Resize selection upward",
            onKeyDown: hotkeysImpl.handleSelectionResizeUp,
        }, {
            combo: "shift+down",
            group: "Table",
            label: "Resize selection downward",
            onKeyDown: hotkeysImpl.handleSelectionResizeDown,
        }, {
            combo: "shift+left",
            group: "Table",
            label: "Resize selection leftward",
            onKeyDown: hotkeysImpl.handleSelectionResizeLeft,
        }, {
            combo: "shift+right",
            group: "Table",
            label: "Resize selection rightward",
            onKeyDown: hotkeysImpl.handleSelectionResizeRight,
        });
    }
    hotkeys.push(...getFocusHotkeys(focusMode, hotkeysImpl));
    if (isSelectionModeEnabled(props, regions_1.RegionCardinality.FULL_TABLE)) {
        hotkeys.push({
            combo: "mod+a",
            group: "Table",
            label: "Select all",
            onKeyDown: hotkeysImpl.handleSelectAllHotkey,
        });
    }
    return hotkeys;
}
function getFocusHotkeys(focusMode, hotkeysImpl) {
    switch (focusMode) {
        case undefined:
            return [];
        case cellTypes_1.FocusMode.ROW:
            return [
                {
                    combo: "up",
                    group: "Table",
                    label: "Move focus row up",
                    onKeyDown: hotkeysImpl.handleFocusMoveUp,
                },
                {
                    combo: "down",
                    group: "Table",
                    label: "Move focus row down",
                    onKeyDown: hotkeysImpl.handleFocusMoveDown,
                },
            ];
        case cellTypes_1.FocusMode.CELL:
            return [
                {
                    combo: "left",
                    group: "Table",
                    label: "Move focus cell left",
                    onKeyDown: hotkeysImpl.handleFocusMoveLeft,
                },
                {
                    combo: "right",
                    group: "Table",
                    label: "Move focus cell right",
                    onKeyDown: hotkeysImpl.handleFocusMoveRight,
                },
                {
                    combo: "up",
                    group: "Table",
                    label: "Move focus cell up",
                    onKeyDown: hotkeysImpl.handleFocusMoveUp,
                },
                {
                    combo: "down",
                    group: "Table",
                    label: "Move focus cell down",
                    onKeyDown: hotkeysImpl.handleFocusMoveDown,
                },
                {
                    allowInInput: true,
                    combo: "tab",
                    group: "Table",
                    label: "Move focus cell tab",
                    onKeyDown: hotkeysImpl.handleFocusMoveRightInternal,
                },
                {
                    allowInInput: true,
                    combo: "shift+tab",
                    group: "Table",
                    label: "Move focus cell shift tab",
                    onKeyDown: hotkeysImpl.handleFocusMoveLeftInternal,
                },
                {
                    allowInInput: true,
                    combo: "enter",
                    group: "Table",
                    label: "Move focus cell enter",
                    onKeyDown: hotkeysImpl.handleFocusMoveDownInternal,
                },
                {
                    allowInInput: true,
                    combo: "shift+enter",
                    group: "Table",
                    label: "Move focus cell shift enter",
                    onKeyDown: hotkeysImpl.handleFocusMoveUpInternal,
                },
            ];
    }
}
/**
 * @returns true if new and old children arrays are the same
 */
function compareChildren(newChildren, oldChildren) {
    return (newChildren.length === oldChildren.length &&
        newChildren.every((child, index) => child.key === oldChildren[index].key));
}
//# sourceMappingURL=tableUtils.js.map