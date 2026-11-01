import { type CellCoordinate, type Region } from "../../regions";
export type ContextMenuRenderer = (context: MenuContext) => React.JSX.Element;
export interface MenuContext {
    /**
     * Returns an array of `Region`s that represent the user-intended context
     * of this menu. If the mouse click was on a selection, the array will
     * contain all selected regions. Otherwise it will have one `Region` that
     * represents the clicked cell (the same `Region` from `getTarget`).
     */
    getRegions: () => Region[];
    /**
     * Returns the list of selected `Region` in the table, regardless of
     * where the users clicked to launch the context menu. For the user-
     * intended regions for this context, use `getRegions` instead.
     */
    getSelectedRegions: () => Region[];
    /**
     * Returns a region containing the single cell that was clicked to launch
     * this context menu.
     */
    getTarget: () => Region;
    /**
     * Returns an array containing all of the unique, potentially non-
     * contiguous, cells contained in all the regions from `getRegions`. The
     * cell coordinates are sorted by rows then columns.
     */
    getUniqueCells: () => CellCoordinate[];
}
export declare class MenuContextImpl implements MenuContext {
    private target;
    private selectedRegions;
    private numRows;
    private numCols;
    private regions;
    constructor(target: Region, selectedRegions: Region[], numRows: number, numCols: number);
    getTarget(): Region;
    getSelectedRegions(): Region[];
    getRegions(): Region[];
    getUniqueCells(): CellCoordinate[];
}
