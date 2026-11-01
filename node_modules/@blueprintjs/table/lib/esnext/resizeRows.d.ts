import type { Rect } from "./common";
import type { CellMapper, Grid } from "./common/grid";
import { type Locator } from "./locator";
export interface ResizeRowsByApproximateHeightOptions {
    /**
     * Approximate width (in pixels) of an average character of text.
     */
    getApproximateCharWidth?: number | CellMapper<number>;
    /**
     * Approximate height (in pixels) of an average line of text.
     */
    getApproximateLineHeight?: number | CellMapper<number>;
    /**
     * Sum of horizontal paddings (in pixels) from the left __and__ right sides
     * of the cell.
     */
    getCellHorizontalPadding?: number | CellMapper<number>;
    /**
     * Number of extra lines to add in case the calculation is imperfect.
     */
    getNumBufferLines?: number | CellMapper<number>;
}
export interface IResizeRowsByApproximateHeightResolvedOptions {
    getApproximateCharWidth: number;
    getApproximateLineHeight: number;
    getCellHorizontalPadding: number;
    getNumBufferLines: number;
}
/**
 * Resizes all rows in the table to the approximate
 * maximum height of wrapped cell content in each row. Works best when each
 * cell contains plain text of a consistent font style (though font style
 * may vary between cells). Since this function uses approximate
 * measurements, results may not be perfect.
 */
export declare function resizeRowsByApproximateHeight(numRows: number, columnWidths: number[], getCellText: CellMapper<string>, options?: ResizeRowsByApproximateHeightOptions): number[];
/**
 * Resize all rows in the table to the height of the tallest visible cell in the specified columns.
 * If no indices are provided, default to using the tallest visible cell from all columns in view.
 */
export declare function resizeRowsByTallestCell(grid: Grid, viewportRect: Rect, locator: Locator, numRows: number, columnIndices?: number | number[]): any[];
