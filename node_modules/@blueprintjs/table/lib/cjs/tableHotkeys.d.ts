import { type FocusedRegion } from "./common/cellTypes";
import { type Grid } from "./common/grid";
import type { TableHeaderDimensions } from "./common/TableHeaderDimensions";
import { type Region, RegionCardinality } from "./regions";
import type { TableProps } from "./tableProps";
import type { TableSnapshot, TableState } from "./tableState";
export interface TableHandlers {
    handleSelection: (selectedRegions: Region[]) => void;
    handleFocus: (focusedRegion: FocusedRegion) => void;
    getEnabledSelectionHandler: (selectionMode: RegionCardinality) => (selectedRegions: Region[]) => void;
    readonly getHeaderDimensions: () => TableHeaderDimensions;
    syncViewportPosition: (snapshot: TableSnapshot) => void;
}
export declare class TableHotkeys {
    private props;
    private state;
    private tableHandlers;
    private grid?;
    constructor(props: TableProps, state: TableState, tableHandlers: TableHandlers);
    setGrid(grid: Grid): void;
    setProps(props: TableProps): void;
    setState(newState: TableState): void;
    private selectAll;
    handleSelectAllHotkey: (e: KeyboardEvent) => void;
    handleSelectionResizeUp: (e: KeyboardEvent) => void;
    handleSelectionResizeDown: (e: KeyboardEvent) => void;
    handleSelectionResizeLeft: (e: KeyboardEvent) => void;
    handleSelectionResizeRight: (e: KeyboardEvent) => void;
    private handleSelectionResize;
    /**
     * Replaces the selected region at the specified array index, with the
     * region provided.
     */
    private updateSelectedRegionAtIndex;
    handleFocusMoveLeft: (e: KeyboardEvent) => void;
    handleFocusMoveLeftInternal: (e: KeyboardEvent) => void;
    handleFocusMoveRight: (e: KeyboardEvent) => void;
    handleFocusMoveRightInternal: (e: KeyboardEvent) => void;
    handleFocusMoveUp: (e: KeyboardEvent) => void;
    handleFocusMoveUpInternal: (e: KeyboardEvent) => void;
    handleFocusMoveDown: (e: KeyboardEvent) => void;
    handleFocusMoveDownInternal: (e: KeyboardEvent) => void;
    private handleFocusMove;
    private static moveFocusedRegionInDirection;
    private static moveFocusedRowInDirection;
    private static moveFocusedCellInDirection;
    private handleFocusMoveInternal;
    private isOutOfBounds;
    private scrollBodyToFocusedRegion;
    private moveFocusCell;
    handleCopy: (e: KeyboardEvent) => void;
}
