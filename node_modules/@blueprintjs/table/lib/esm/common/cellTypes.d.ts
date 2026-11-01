export interface CellCoordinates {
    col: number;
    row: number;
}
export interface FocusedCellCoordinates extends CellCoordinates {
    focusSelectionIndex: number;
}
export declare enum FocusMode {
    CELL = "cell",
    ROW = "row"
}
export interface FocusedCell extends FocusedCellCoordinates {
    type: FocusMode.CELL;
}
export interface FocusedRow {
    type: FocusMode.ROW;
    row: number;
    focusSelectionIndex: number;
}
export type FocusedRegion = FocusedCell | FocusedRow;
