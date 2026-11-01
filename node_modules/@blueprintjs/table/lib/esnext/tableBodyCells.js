import { jsx as _jsx } from "react/jsx-runtime";
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
import classNames from "classnames";
import { cloneElement } from "react";
import { AbstractComponent, Utils as CoreUtils } from "@blueprintjs/core";
import { emptyCellRenderer } from "./cell/cell";
import { Batcher } from "./common/batcher";
import { FocusMode } from "./common/cellTypes";
import * as Classes from "./common/classes";
import { Rect } from "./common/rect";
import { RenderMode } from "./common/renderMode";
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
export class TableBodyCells extends AbstractComponent {
    static defaultProps = {
        renderMode: RenderMode.BATCH,
    };
    static cellReactKey(rowIndex, columnIndex) {
        return `cell-${rowIndex}-${columnIndex}`;
    }
    batcher = new Batcher();
    /**
     * Set this flag to true in componentDidUpdate() when we call forceUpdate() to avoid an extra
     * unnecessary update cycle.
     */
    didForceUpdate = false;
    componentDidMount() {
        this.maybeInvokeOnCompleteRender();
    }
    shouldComponentUpdate(nextProps) {
        return (!CoreUtils.shallowCompareKeys(nextProps, this.props, {
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
        const shouldResetBatcher = !CoreUtils.shallowCompareKeys(prevProps, this.props, {
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
        const cells = renderMode === RenderMode.BATCH ? this.renderBatchedCells() : this.renderAllCells();
        return _jsx("div", { className: Classes.TABLE_BODY_CELLS, children: cells });
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
        let baseCell = isGhost ? emptyCellRenderer() : cellRenderer(rowIndex, columnIndex);
        // cellRenderer still may return null
        baseCell = baseCell == null ? emptyCellRenderer() : baseCell;
        const className = classNames(cellClassNames(rowIndex, columnIndex), extremaClasses, {
            [Classes.TABLE_CELL_GHOST]: isGhost,
            [Classes.TABLE_CELL_LEDGER_ODD]: rowIndex % 2 === 1,
            [Classes.TABLE_CELL_LEDGER_EVEN]: rowIndex % 2 === 0,
        }, baseCell.props.className);
        const key = TableBodyCells.cellReactKey(rowIndex, columnIndex);
        const rect = isGhost ? grid.getGhostCellRect(rowIndex, columnIndex) : grid.getCellRect(rowIndex, columnIndex);
        const cellLoading = baseCell.props.loading != null ? baseCell.props.loading : loading;
        const style = { ...baseCell.props.style, ...Rect.style(rect) };
        const isFocused = this.isCellFocused(rowIndex, columnIndex);
        return cloneElement(baseCell, {
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
            case FocusMode.CELL:
                return focusedRegion.row === rowIndex && focusedRegion.col === columnIndex;
            case FocusMode.ROW:
                return focusedRegion.row === rowIndex;
            case undefined:
                return false;
        }
    }
    // Callbacks
    // =========
    maybeInvokeOnCompleteRender() {
        const { onCompleteRender, renderMode } = this.props;
        if (renderMode === RenderMode.NONE || (renderMode === RenderMode.BATCH && this.batcher.isDone())) {
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
/**
 * Returns the array of class names that must be applied to each table
 * cell so that we can locate any cell based on its coordinate.
 */
export function cellClassNames(rowIndex, columnIndex) {
    return [Classes.rowCellIndexClass(rowIndex), Classes.columnCellIndexClass(columnIndex)];
}
//# sourceMappingURL=tableBodyCells.js.map