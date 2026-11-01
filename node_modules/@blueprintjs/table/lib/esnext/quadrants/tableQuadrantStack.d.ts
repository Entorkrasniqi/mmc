import { AbstractComponent, type Props } from "@blueprintjs/core";
import { Grid } from "../common/grid";
import type { TableLoadingOption } from "../regions";
import { QuadrantType } from "./tableQuadrant";
interface TableQuadrantStackProps extends Props {
    /**
     * A callback that receives a `ref` to the main quadrant's table-body element.
     */
    bodyRef?: React.Ref<HTMLDivElement>;
    /**
     * A callback that receives a `ref` to the main quadrant's column-header container.
     */
    columnHeaderRef?: React.Ref<HTMLDivElement>;
    /**
     * The grid computes sizes of cells, rows, or columns from the
     * configurable `columnWidths` and `rowHeights`.
     */
    grid: Grid;
    /**
     * An optional callback for reacting to column-resize events.
     */
    handleColumnResizeGuide?: (verticalGuides: number[]) => void;
    /**
     * An optional callback for reacting to column-reordering events.
     */
    handleColumnsReordering?: (verticalGuides: number[]) => void;
    /**
     * An optional callback for reacting to row-resize events.
     */
    handleRowResizeGuide?: (horizontalGuides: number[]) => void;
    /**
     * An optional callback for reacting to column-reordering events.
     */
    handleRowsReordering?: (horizontalGuides: number[]) => void;
    /**
     * Whether horizontal scrolling is currently disabled.
     *
     * @default false
     */
    isHorizontalScrollDisabled?: boolean;
    /**
     * If `false`, hides the row headers and settings menu. Affects the layout
     * of the table, so we need to know when this changes in order to
     * synchronize quadrant sizes properly.
     *
     * REQUIRES QUADRANT RESYNC
     *
     * @default true
     */
    enableRowHeader?: boolean;
    /**
     * Whether vertical scrolling is currently disabled.
     *
     * @default false
     */
    isVerticalScrollDisabled?: boolean;
    /**
     * A list of `TableLoadingOption`. Loading cells may have different sizes
     * from potentially custom cells in the header or body, so we need to know
     * when the loading states change in order to synchronize quadrant sizes
     * properly.
     *
     * REQUIRES QUADRANT RESYNC
     */
    loadingOptions?: TableLoadingOption[];
    /**
     * The number of columns. Affects the layout of the table, so we need to
     * know when this changes in order to synchronize quadrant sizes properly.
     *
     * REQUIRES QUADRANT RESYNC
     */
    numColumns?: number;
    /**
     * The number of frozen columns. Affects the layout of the table, so we need
     * to know when this changes in order to synchronize quadrant sizes
     * properly.
     *
     * REQUIRES QUADRANT RESYNC
     */
    numFrozenColumns: number;
    /**
     * The number of frozen rows. Affects the layout of the table, so we need to
     * know when this changes in order to synchronize quadrant sizes properly.
     *
     * REQUIRES QUADRANT RESYNC
     */
    numFrozenRows: number;
    /**
     * The number of rows. Affects the layout of the table, so we need to know
     * when this changes in order to synchronize quadrant sizes properly.
     *
     * REQUIRES QUADRANT RESYNC
     */
    numRows?: number;
    /**
     * An optional callback invoked the quadrants are scrolled.
     */
    onScroll?: React.EventHandler<React.SyntheticEvent<HTMLElement>>;
    /**
     * A callback that receives a `ref` to the main-quadrant element.
     */
    quadrantRef?: React.Ref<HTMLDivElement>;
    /**
     * A callback that renders either all of or just frozen sections of the table body.
     * May return undefined if the table is not attached to the DOM yet.
     */
    bodyRenderer: (quadrantType: QuadrantType, showFrozenRowsOnly?: boolean, showFrozenColumnsOnly?: boolean) => React.JSX.Element | undefined;
    /**
     * A callback that renders either all of or just the frozen section of the column header.
     * May return undefined if the table is not attached to the DOM yet.
     */
    columnHeaderRenderer?: (refHandler: React.Ref<HTMLDivElement>, resizeHandler: (verticalGuides: number[] | null) => void, reorderingHandler: (oldIndex: number, newIndex: number, length: number) => void, showFrozenColumnsOnly?: boolean) => React.JSX.Element | undefined;
    /**
     * A callback that renders the table menu (the rectangle in the top-left corner).
     */
    menuRenderer?: (refHandler: React.Ref<HTMLDivElement> | undefined) => React.JSX.Element;
    /**
     * A callback that renders either all of or just the frozen section of the row header.
     * May return undefined if the table is not attached to the DOM yet.
     */
    rowHeaderRenderer?: (refHandler: React.Ref<HTMLDivElement>, resizeHandler: (verticalGuides: number[] | null) => void, reorderingHandler: (oldIndex: number, newIndex: number, length: number) => void, showFrozenRowsOnly?: boolean) => React.JSX.Element | undefined;
    renderScrollIndicatorOverlay?: (scrollBarWidth: number, columnHeaderHeight: number) => React.JSX.Element | undefined;
    /**
     * A callback that receives a `ref` to the main quadrant's row-header container.
     */
    rowHeaderRef?: React.Ref<HTMLDivElement>;
    /**
     * A callback that receives a `ref` to the main quadrant's scroll-container element.
     */
    scrollContainerRef?: React.Ref<HTMLDivElement>;
    /**
     * Whether "scroll" and "wheel" events should be throttled using
     * requestAnimationFrame. Disabling this can be useful for unit testing,
     * because tests can then be synchronous.
     *
     * @default true
     */
    throttleScrolling?: boolean;
    /**
     * The amount of time in milliseconds the component should wait before
     * synchronizing quadrant sizes and offsets after the user has stopped
     * scrolling. If this value is negative, the updates will happen
     * synchronously (this is helpful for unit testing).
     *
     * @default 500
     */
    viewSyncDelay?: number;
    /**
     * If `true`, adds an interaction bar on top of all column header cells, and
     * moves interaction triggers into it. Affects the layout of the table, so
     * we need to know when this changes in order to synchronize quadrant sizes
     * properly.
     *
     * This value defaults to `undefined` so that, by default, it won't override
     * the `enableColumnInteractionBar` values that you might have provided directly to
     * each `<ColumnHeaderCell>`.
     *
     * REQUIRES QUADRANT RESYNC
     *
     * @default undefined
     */
    enableColumnInteractionBar?: boolean;
    /**
     * Flag indicating that both the column headers (if present)
     * and row headers (if present) have been rendered and mounted, including any
     * custom renderers which may affect quadrant layout measurements.
     */
    didHeadersMount: boolean;
    /**
     * If `false`, hides the column headers. Affects the layout
     * of the table, so we need to know when this changes in order to
     * synchronize quadrant sizes properly.
     *
     * REQUIRES QUADRANT RESYNC
     *
     * @default true
     */
    enableColumnHeader?: boolean;
}
export declare class TableQuadrantStack extends AbstractComponent<TableQuadrantStackProps> {
    static defaultProps: Partial<TableQuadrantStackProps>;
    private quadrantRefs;
    private quadrantRefHandlers;
    private wasMainQuadrantScrollTriggeredByWheelEvent;
    private throttledHandleMainQuadrantScroll;
    private throttledHandleWheel;
    private cancelPendingViewSync?;
    private cache;
    constructor(props: TableQuadrantStackProps);
    /**
     * Scroll the main quadrant to the specified scroll offset, keeping all other quadrants in sync.
     */
    scrollToPosition(scrollLeft: number, scrollTop: number): void;
    /**
     * Synchronizes quadrant sizes and scroll offsets based on the current
     * column, row, and header sizes. Useful for correcting quadrant sizes after
     * explicitly resizing columns and rows, for instance.
     *
     * Invoking this method imperatively is cheaper than providing columnWidths
     * or rowHeights array props to TableQuadrantStack and forcing it to run
     * expensive array diffs upon every update.
     */
    synchronizeQuadrantViews(): void;
    componentDidMount(): void;
    componentDidUpdate(prevProps: TableQuadrantStackProps): void;
    render(): import("react/jsx-runtime").JSX.Element;
    private generateQuadrantRefHandlers;
    private renderTableOverlay;
    private renderMainQuadrantMenu;
    private renderTopQuadrantMenu;
    private renderLeftQuadrantMenu;
    private renderTopLeftQuadrantMenu;
    private renderMainQuadrantColumnHeader;
    private renderTopQuadrantColumnHeader;
    private renderLeftQuadrantColumnHeader;
    private renderTopLeftQuadrantColumnHeader;
    private renderMainQuadrantRowHeader;
    private renderTopQuadrantRowHeader;
    private renderLeftQuadrantRowHeader;
    private renderTopLeftQuadrantRowHeader;
    private handleMainQuadrantScroll;
    private handleWheel;
    private getNextScrollOffset;
    private handleColumnResizeGuideMain;
    private handleColumnResizeGuideTop;
    private handleColumnResizeGuideLeft;
    private handleColumnResizeGuideTopLeft;
    private invokeColumnResizeHandler;
    private handleRowResizeGuideMain;
    private handleRowResizeGuideTop;
    private handleRowResizeGuideLeft;
    private handleRowResizeGuideTopLeft;
    private invokeRowResizeHandler;
    private handleColumnsReordering;
    private handleRowsReordering;
    private emitRefs;
    private syncQuadrantViewsDebounced;
    private syncQuadrantViews;
    private maybeSetQuadrantSizes;
    private maybesSetQuadrantSize;
    private maybeSetQuadrantPositionOffset;
    private maybesSetQuadrantRowHeaderSizes;
    private maybeSetQuadrantRowHeaderSize;
    private maybeSetQuadrantMenuElementSizes;
    private maybeSetQuadrantMenuElementSize;
    private maybeSetQuadrantScrollOffset;
    private handleScrollOffsetChange;
    private updateScrollContainerClientSize;
    private maybeIncreaseToMinColHeaderHeight;
    /** Returns true the cumulative width of all frozen columns in the grid changed. */
    private didFrozenColumnWidthsChange;
    /** Returns true the cumulative height of all frozen rows in the grid changed. */
    private didFrozenRowHeightsChange;
    /**
     * Returns the width or height of *only the grid* in the secondary quadrants
     * (TOP, LEFT, TOP_LEFT), based on the number of frozen rows and columns.
     */
    private getSecondaryQuadrantGridSize;
    /**
     * Measures the desired width of the row header based on its tallest
     * contents.
     */
    private measureDesiredRowHeaderWidth;
    /**
     * Measures the desired height of the column header based on its tallest
     * contents.
     */
    private measureDesiredColumnHeaderHeight;
    private shouldRenderLeftQuadrants;
    private adjustVerticalGuides;
    private adjustHorizontalGuides;
}
export {};
