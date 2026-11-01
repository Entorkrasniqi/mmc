import { Grid } from "./common/grid";
import { Rect } from "./common/rect";
export interface Locator {
    /**
     * Returns the width that a column must be to contain all the content of
     * its cells without truncating or wrapping.
     */
    getWidestVisibleCellInColumn: (columnIndex: number) => number;
    /**
     * Gets the viewport rect.
     */
    getViewportRect(): Rect;
    /**
     * Returns the height of the tallest cell in a given column -- specifically,
     * tallest as in how tall the cell would have to be to display all the content in it
     */
    getTallestVisibleCellInColumn: (columnIndex: number) => number;
    /**
     * Locates a column's index given the client X coordinate. Returns -1 if
     * the coordinate is not over a column.
     * If `useMidpoint` is `true`, returns the index of the column whose left
     * edge is closest, splitting on the midpoint of each column.
     */
    convertPointToColumn: (clientX: number, useMidpoint?: boolean) => number;
    /**
     * Locates a row's index given the client Y coordinate. Returns -1 if
     * the coordinate is not over a row.
     * If `useMidpoint` is `true`, returns the index of the row whose top
     * edge is closest, splitting on the midpoint of each row.
     */
    convertPointToRow: (clientY: number, useMidpoint?: boolean) => number;
    /**
     * Locates a cell's row and column index given the client X and Y
     * coordinates.
     */
    convertPointToCell: (clientX: number, clientY: number) => {
        col: number;
        row: number;
    };
    /**
     * Updates the grid.
     */
    setGrid(grid: Grid): this;
    setNumFrozenRows(numFrozenRows: number): this;
    setNumFrozenColumns(numFrozenColumns: number): this;
    /**
     * @returns whether the rendered rows overflow the visible viewport vertically, helpful for scrolling calculations
     */
    hasVerticalOverflowOrExactFit(columnHeaderHeight: number, viewportRect: Rect): boolean;
    /**
     * @returns whether the rendered columns overflow the visible viewport horizontally, helpful for scrolling calculations
     */
    hasHorizontalOverflowOrExactFit(rowHeaderWidth: number, viewportRect: Rect): boolean;
}
export declare class LocatorImpl implements Locator {
    private tableElement;
    private scrollContainerElement;
    private cellContainerElement;
    static CELL_HORIZONTAL_PADDING: number;
    private grid;
    private numFrozenRows;
    private numFrozenColumns;
    constructor(tableElement: HTMLElement, scrollContainerElement: HTMLElement, cellContainerElement: HTMLElement);
    setGrid(grid: Grid): this;
    setNumFrozenRows(numFrozenRows: number): this;
    setNumFrozenColumns(numFrozenColumns: number): this;
    getViewportRect(): Rect;
    getWidestVisibleCellInColumn(columnIndex: number): number;
    getTallestVisibleCellInColumn(columnIndex: number): number;
    /**
     * Pass in an already-computed viewport rect here, if available, to reduce DOM reads.
     *
     * @returns whether the rendered rows overflow or exactly fit the visible viewport vertically, helpful for scrolling calculations
     */
    hasVerticalOverflowOrExactFit(columnHeaderHeight?: number, viewportRect?: Rect): boolean;
    /**
     * Pass in an already-computed viewport rect here, if available, to reduce DOM reads.
     *
     * @returns whether the rendered columns overflow or exactly fit the visible viewport horizontally, helpful for scrolling calculations
     */
    hasHorizontalOverflowOrExactFit(rowHeaderWidth?: number, viewportRect?: Rect): boolean;
    convertPointToColumn(clientX: number, useMidpoint?: boolean): number;
    convertPointToRow(clientY: number, useMidpoint?: boolean): number;
    convertPointToCell(clientX: number, clientY: number): {
        col: number;
        row: number;
    };
    private getColumnCellSelector;
    private getTableRect;
    private convertCellIndexToClientX;
    private convertCellMidpointToClientX;
    private convertCellIndexToClientY;
    private convertCellMidpointToClientY;
    private toGridX;
    private toGridY;
}
