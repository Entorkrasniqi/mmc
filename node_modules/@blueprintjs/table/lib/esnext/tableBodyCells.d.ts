import { AbstractComponent, type Props } from "@blueprintjs/core";
import { type CellRenderer } from "./cell/cell";
import { type FocusedRegion } from "./common/cellTypes";
import type { ColumnIndices, Grid, RowIndices } from "./common/grid";
import { Rect } from "./common/rect";
import { RenderMode } from "./common/renderMode";
export interface TableBodyCellsProps extends RowIndices, ColumnIndices, Props {
    /**
     * A cell renderer for the cells in the body.
     */
    cellRenderer: CellRenderer;
    /**
     * The coordinates of the currently focused region, for setting the "isFocused" prop on cells.
     */
    focusedRegion?: FocusedRegion;
    /**
     * The grid computes sizes of cells, rows, or columns from the
     * configurable `columnWidths` and `rowHeights`.
     */
    grid: Grid;
    /**
     * If true, all `Cell`s render their loading state except for those who have
     * their `loading` prop explicitly set to false.
     */
    loading: boolean;
    /**
     * An optional callback invoked when all cells in view have completely rendered.
     */
    onCompleteRender?: () => void;
    /**
     * Dictates how cells should be rendered. This component doesn't support
     * `RenderMode.BATCH_ON_UPDATE`, because there are actually multiple updates
     * that need to happen at higher levels before the table is considered fully
     * "mounted"; thus, we let higher components tell us when to switch modes.
     *
     * @default RenderMode.BATCH
     */
    renderMode?: RenderMode.BATCH | RenderMode.NONE;
    /**
     * The `Rect` bounds of the visible viewport with respect to its parent
     * scrollable pane. While not directly used by the component, this prop is
     * necessary for shouldComponentUpdate logic to run properly.
     */
    viewportRect: Rect;
}
export declare class TableBodyCells extends AbstractComponent<TableBodyCellsProps> {
    static defaultProps: {
        renderMode: RenderMode;
    };
    private static cellReactKey;
    private batcher;
    /**
     * Set this flag to true in componentDidUpdate() when we call forceUpdate() to avoid an extra
     * unnecessary update cycle.
     */
    private didForceUpdate;
    componentDidMount(): void;
    shouldComponentUpdate(nextProps: TableBodyCellsProps): boolean;
    componentDidUpdate(prevProps: TableBodyCellsProps): void;
    componentWillUnmount(): void;
    render(): import("react/jsx-runtime").JSX.Element;
    private renderBatchedCells;
    private renderAllCells;
    private renderNewCell;
    private renderCell;
    private isCellFocused;
    private maybeInvokeOnCompleteRender;
    private didViewportRectChange;
}
/**
 * Returns the array of class names that must be applied to each table
 * cell so that we can locate any cell based on its coordinate.
 */
export declare function cellClassNames(rowIndex: number, columnIndex: number): string[];
