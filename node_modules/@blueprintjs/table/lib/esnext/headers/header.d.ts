import { Component } from "react";
import type { Grid } from "../common";
import type { FocusedRegion, FocusMode } from "../common/cellTypes";
import type { ClientCoordinates } from "../interactions/dragTypes";
import { type ReorderableProps } from "../interactions/reorderable";
import type { LockableLayout, Orientation } from "../interactions/resizeHandle";
import { type SelectableProps } from "../interactions/selectable";
import type { Locator } from "../locator";
import { type Region, RegionCardinality } from "../regions";
import type { HeaderCellProps } from "./headerCell";
export type HeaderCellRenderer = (index: number) => React.ReactElement<HeaderCellProps>;
export interface HeaderProps extends LockableLayout, ReorderableProps, SelectableProps {
    /**
     * The the type shape allowed for focus areas. Can be cell, row, or none.
     */
    focusMode: FocusMode | undefined;
    /**
     * The currently focused region.
     */
    focusedRegion?: FocusedRegion;
    /**
     * The grid computes sizes of cells, rows, or columns from the
     * configurable `columnWidths` and `rowHeights`.
     */
    grid: Grid;
    /**
     * Enables/disables the resize interaction.
     *
     * @default true
     */
    isResizable?: boolean;
    /**
     * Locates the row/column/cell given a mouse event.
     */
    locator: Locator;
    /**
     * If true, all header cells render their loading state except for those
     * who have their `loading` prop explicitly set to false.
     *
     * @default false;
     */
    loading?: boolean;
    /**
     * When the user reorders something, this callback is called with the new
     * focus region for the newly selected set of regions.
     */
    onFocusedRegion: (focusedRegion: FocusedRegion) => void;
    /**
     * This callback is called while the user is resizing a header cell. The guides
     * array contains pixel offsets for where to display the resize guides in
     * the table body's overlay layer. `guides` will be null if this is the end
     * or cancellation of a resize interaction.
     */
    onResizeGuide: (guides: number[] | null) => void;
    /**
     * The content to be rendered inside the header.
     */
    children?: React.ReactNode;
}
/**
 * These are additional props passed internally from ColumnHeader and RowHeader.
 * They don't need to be exposed to the outside world.
 */
export interface InternalHeaderProps extends HeaderProps {
    /**
     * The cardinality of a fully selected region. Should be FULL_COLUMNS for column headers and
     * FULL_ROWS for row headers.
     */
    fullRegionCardinality: RegionCardinality;
    /**
     * An optional callback invoked when the user double-clicks a resize handle, if resizing is enabled.
     */
    handleResizeDoubleClick?: (index: number) => void;
    /**
     * The name of the header-cell prop specifying whether the header cell is reorderable or not.
     */
    headerCellIsReorderablePropName: string;
    /**
     * The name of the header-cell prop specifying whether the header cell is selected or not.
     */
    headerCellIsSelectedPropName: string;
    /**
     * The highest cell index to render.
     */
    indexEnd: number;
    /**
     * The lowest cell index to render.
     */
    indexStart: number;
    /**
     * The maximum permitted size of the header in pixels. Corresponds to a width for column headers and
     * a height for row headers.
     */
    maxSize: number;
    /**
     * The minimum permitted size of the header in pixels. Corresponds to a width for column headers and
     * a height for row headers.
     */
    minSize: number;
    /**
     * The orientation of the resize handle. Should be VERTICAL for column headers and HORIZONTAL
     * for row headers.
     */
    resizeOrientation: Orientation;
    /**
     * An array containing the table's selection Regions.
     */
    selectedRegions: Region[];
    /**
     * Converts a point on the screen to a row or column index in the table grid.
     */
    convertPointToIndex: (clientXOrY: number, useMidpoint?: boolean) => number;
    /**
     * Provides any extrema classes for the provided index range in the table grid.
     */
    getCellExtremaClasses: (index: number, indexEnd: number) => string[];
    /**
     * Provides the index class for the cell. Should be Classes.columnCellIndexClass for column
     * headers or Classes.rowCellIndexClass for row headers.
     */
    getCellIndexClass: (index: number) => string;
    /**
     * Returns the size of the specified header cell in pixels. Corresponds to a width for column
     * headers and a height for row headers.
     */
    getCellSize: (index: number) => number;
    /**
     * Returns the relevant single coordinate from the provided client coordinates. Should return
     * the x coordinate for column headers and the y coordinate for row headers.
     */
    getDragCoordinate: (clientCoords: ClientCoordinates) => number;
    /**
     * A callback that returns the CSS index class for the specified index. Should be
     * Classes.columnIndexClass for column headers and Classes.rowIndexClass for row headers.
     */
    getIndexClass: (index: number) => string;
    /**
     * Given a mouse event, returns the relevant client coordinate (clientX or clientY). Should be
     * clientX for column headers and clientY for row headers.
     */
    getMouseCoordinate: (event: MouseEvent) => number;
    /**
     * Invoked when a resize interaction ends, if resizing is enabled.
     */
    handleResizeEnd: (index: number, size: number) => void;
    /**
     * Invoked whenever the size changes during a resize interaction, if resizing is enabled.
     */
    handleSizeChanged: (index: number, size: number) => void;
    /**
     * Returns true if the specified cell (and therefore the full column/row) is selected.
     */
    isCellSelected: (index: number) => boolean;
    /**
     * Returns true if the specified cell is at a ghost index.
     */
    isGhostIndex: (index: number) => boolean;
    /**
     * A callback that renders a ghost cell for the provided index.
     */
    ghostCellRenderer: (index: number, extremaClasses: string[]) => React.JSX.Element;
    /**
     * A callback that renders a regular header cell at the provided index.
     */
    headerCellRenderer: (index: number) => React.JSX.Element | null;
    /**
     * Converts a range to a region. This should be Regions.column for column headers and
     * Regions.row for row headers.
     */
    toRegion: (index1: number, index2?: number) => Region;
    /**
     * A callback that wraps the rendered cell components in additional parent elements as needed.
     */
    wrapCells: (cells: Array<React.ReactElement<any>>) => React.JSX.Element;
}
export interface HeaderState {
    /**
     * Whether the component has a valid selection specified either via props
     * (i.e. controlled mode) or via a completed drag-select interaction. When
     * true, DragReorderable will know that it can override the click-and-drag
     * interactions that would normally be reserved for drag-select behavior.
     */
    hasValidSelection: boolean;
}
export declare class Header extends Component<InternalHeaderProps, HeaderState> {
    protected activationIndex: number | null;
    private cellRefs;
    private reorderHandleRefs;
    constructor(props: InternalHeaderProps);
    componentDidUpdate(_: InternalHeaderProps, prevState: HeaderState): void;
    shouldComponentUpdate(nextProps: InternalHeaderProps, nextState: HeaderState): boolean;
    render(): import("react").JSX.Element;
    private isSelectedRegionsControlledAndNonEmpty;
    private convertEventToIndex;
    private locateClick;
    private locateDragForSelection;
    private locateDragForReordering;
    private renderCells;
    private renderNewCell;
    private renderCell;
    private isReorderHandleEnabled;
    private maybeRenderReorderHandle;
    private isColumnHeader;
    private wrapInDragReorderable;
    private handleDragSelectableSelection;
    private handleDragSelectableSelectionEnd;
    private isDragSelectableDisabled;
    private isDragReorderableDisabled;
    private isEntireCellTargetReorderable;
}
