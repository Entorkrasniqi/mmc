"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TableBodyCells = void 0;
exports.cellClassNames = cellClassNames;
const tslib_1 = require("tslib");
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
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const cell_1 = require("./cell/cell");
const batcher_1 = require("./common/batcher");
const cellTypes_1 = require("./common/cellTypes");
const Classes = tslib_1.__importStar(require("./common/classes"));
const rect_1 = require("./common/rect");
const renderMode_1 = require("./common/renderMode");
const SHALLOW_COMPARE_DENYLIST = ["viewportRect"];
/**
 * We don't want to reset the batcher when this set of keys changes. Any other
 * changes should reset the batcher's internal cache.
 */
const BATCHER_RESET_PROP_KEYS_DENYLIST = [
    "columnIndexEnd",
    "columnIndexStart",
    "rowIndexEnd",
    "rowIndexStart",
];
class TableBodyCells extends core_1.AbstractComponent {
    static defaultProps = {
        renderMode: renderMode_1.RenderMode.BATCH,
    };
    static cellReactKey(rowIndex, columnIndex) {
        return `cell-${rowIndex}-${columnIndex}`;
    }
    batcher = new batcher_1.Batcher();
    /**
     * Set this flag to true in componentDidUpdate() when we call forceUpdate() to avoid an extra
     * unnecessary update cycle.
     */
    didForceUpdate = false;
    componentDidMount() {
        this.maybeInvokeOnCompleteRender();
    }
    shouldComponentUpdate(nextProps) {
        return (!core_1.Utils.shallowCompareKeys(nextProps, this.props, {
            exclude: SHALLOW_COMPARE_DENYLIST,
        }) ||
            // "viewportRect" is not a plain object, so we can't just deep
            // compare; we need custom logic.
            this.didViewportRectChange(nextProps.viewportRect, this.props.viewportRect));
    }
    componentDidUpdate(prevProps) {
        if (this.didForceUpdate) {
            this.didForceUpdate = false;
            return;
        }
        const shouldResetBatcher = !core_1.Utils.shallowCompareKeys(prevProps, this.props, {
            exclude: BATCHER_RESET_PROP_KEYS_DENYLIST,
        });
        if (shouldResetBatcher) {
            this.batcher.reset();
            // At this point, the batcher is reset, but it doesn't have a chance to re-run since render() is not called
            // by default after this lifecycle method. This causes issues like https://github.com/palantir/blueprint/issues/5193.
            // We can run forceUpdate() to re-render, but must take care to set a local flag indicating that we are doing so,
            // so that this lifecycle method doesn't get re-run as well within the same forced update cycle.
            this.didForceUpdate = true;
            this.forceUpdate();
        }
        this.maybeInvokeOnCompleteRender();
    }
    componentWillUnmount() {
        this.batcher.cancelOutstandingCallback();
    }
    render() {
        const { renderMode } = this.props;
        const cells = renderMode === renderMode_1.RenderMode.BATCH ? this.renderBatchedCells() : this.renderAllCells();
        return (0, jsx_runtime_1.jsx)("div", { className: Classes.TABLE_BODY_CELLS, children: cells });
    }
    // Render modes
    // ============
    renderBatchedCells() {
        const { columnIndexEnd, columnIndexStart, rowIndexEnd, rowIndexStart } = this.props;
        // render cells in batches
        this.batcher.startNewBatch();
        for (let rowIndex = rowIndexStart; rowIndex <= rowIndexEnd; rowIndex++) {
            for (let columnIndex = columnIndexStart; columnIndex <= columnIndexEnd; columnIndex++) {
                this.batcher.addArgsToBatch(rowIndex, columnIndex);
            }
        }
        this.batcher.removeOldAddNew(this.renderNewCell);
        if (!this.batcher.isDone()) {
            this.batcher.idleCallback(() => this.forceUpdate());
        }
        return this.batcher.getList();
    }
    renderAllCells() {
        const { columnIndexEnd, columnIndexStart, rowIndexEnd, rowIndexStart } = this.props;
        const cells = [];
        const cellsArgs = [];
        for (let rowIndex = rowIndexStart; rowIndex <= rowIndexEnd; rowIndex++) {
            for (let columnIndex = columnIndexStart; columnIndex <= columnIndexEnd; columnIndex++) {
                cells.push(this.renderNewCell(rowIndex, columnIndex));
                cellsArgs.push([rowIndex, columnIndex]);
            }
        }
        // pretend we did an entire rendering pass using the batcher. that way,
        // if we switch from `RenderMode.NONE` to `RenderMode.BATCH`, we don't
        // have to re-paint every cell still in view.
        this.batcher.setList(cellsArgs, cells);
        return cells;
    }
    // Cell renderers
    // ==============
    renderNewCell = (rowIndex, columnIndex) => {
        const { columnIndexEnd, grid, rowIndexEnd } = this.props;
        const extremaClasses = grid.getExtremaClasses(rowIndex, columnIndex, rowIndexEnd, columnIndexEnd);
        const isGhost = grid.isGhostIndex(rowIndex, columnIndex);
        return this.renderCell(rowIndex, columnIndex, extremaClasses, isGhost);
    };
    renderCell = (rowIndex, columnIndex, extremaClasses, isGhost) => {
        const { cellRenderer, loading, grid } = this.props;
        let baseCell = isGhost ? (0, cell_1.emptyCellRenderer)() : cellRenderer(rowIndex, columnIndex);
        // cellRenderer still may return null
        baseCell = baseCell == null ? (0, cell_1.emptyCellRenderer)() : baseCell;
        const className = (0, classnames_1.default)(cellClassNames(rowIndex, columnIndex), extremaClasses, {
            [Classes.TABLE_CELL_GHOST]: isGhost,
            [Classes.TABLE_CELL_LEDGER_ODD]: rowIndex % 2 === 1,
            [Classes.TABLE_CELL_LEDGER_EVEN]: rowIndex % 2 === 0,
        }, baseCell.props.className);
        const key = TableBodyCells.cellReactKey(rowIndex, columnIndex);
        const rect = isGhost ? grid.getGhostCellRect(rowIndex, columnIndex) : grid.getCellRect(rowIndex, columnIndex);
        const cellLoading = baseCell.props.loading != null ? baseCell.props.loading : loading;
        const style = { ...baseCell.props.style, ...rect_1.Rect.style(rect) };
        const isFocused = this.isCellFocused(rowIndex, columnIndex);
        return (0, react_1.cloneElement)(baseCell, {
            className,
            isFocused,
            key,
            loading: cellLoading,
            style,
        });
    };
    isCellFocused(rowIndex, columnIndex) {
        const { focusedRegion } = this.props;
        switch (focusedRegion?.type) {
            case cellTypes_1.FocusMode.CELL:
                return focusedRegion.row === rowIndex && focusedRegion.col === columnIndex;
            case cellTypes_1.FocusMode.ROW:
                return focusedRegion.row === rowIndex;
            case undefined:
                return false;
        }
    }
    // Callbacks
    // =========
    maybeInvokeOnCompleteRender() {
        const { onCompleteRender, renderMode } = this.props;
        if (renderMode === renderMode_1.RenderMode.NONE || (renderMode === renderMode_1.RenderMode.BATCH && this.batcher.isDone())) {
            onCompleteRender?.();
        }
    }
    // Other
    // =====
    didViewportRectChange = (nextViewportRect, currViewportRect) => {
        if (nextViewportRect == null && currViewportRect == null) {
            return false;
        }
        else if (nextViewportRect == null || currViewportRect == null) {
            return true;
        }
        else {
            return !nextViewportRect.equals(currViewportRect);
        }
    };
}
exports.TableBodyCells = TableBodyCells;
/**
 * Returns the array of class names that must be applied to each table
 * cell so that we can locate any cell based on its coordinate.
 */
function cellClassNames(rowIndex, columnIndex) {
    return [Classes.rowCellIndexClass(rowIndex), Classes.columnCellIndexClass(columnIndex)];
}
//# sourceMappingURL=tableBodyCells.js.map