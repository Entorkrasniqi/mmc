import { AbstractComponent, type ContextMenuContentProps } from "@blueprintjs/core";
import type { FocusedRegion, FocusMode } from "./common/cellTypes";
import { RenderMode } from "./common/renderMode";
import { type ContextMenuRenderer } from "./interactions/menus";
import { type SelectableProps } from "./interactions/selectable";
import type { Locator } from "./locator";
import { type TableBodyCellsProps } from "./tableBodyCells";
export interface TableBodyProps extends SelectableProps, TableBodyCellsProps {
    /**
     * An optional callback for displaying a context menu when right-clicking
     * on the table body. The callback is supplied with a `MenuContext`
     * containing the `Region`s of interest.
     */
    bodyContextMenuRenderer?: ContextMenuRenderer;
    /**
     * The the type shape allowed for focus areas. Can be cell, row, or none.
     */
    focusMode: FocusMode | undefined;
    /**
     * Locates the row/column/cell given a mouse event.
     */
    locator: Locator;
    /**
     * The number of columns to freeze to the left side of the table, counting from the leftmost column.
     */
    numFrozenColumns?: number;
    /**
     * The number of rows to freeze to the top of the table, counting from the topmost row.
     */
    numFrozenRows?: number;
    /**
     * Callback invoked when the focused region changes
     */
    onFocusedRegion: (focusedRegion: FocusedRegion) => void;
}
export declare class TableBody extends AbstractComponent<TableBodyProps> {
    static defaultProps: {
        loading: boolean;
        renderMode: RenderMode;
    };
    private activationCell;
    private containerRef;
    shouldComponentUpdate(nextProps: TableBodyProps): boolean;
    render(): import("react/jsx-runtime").JSX.Element;
    renderContextMenu: ({ mouseEvent }: ContextMenuContentProps) => import("react").JSX.Element | undefined;
    private handleContextMenu;
    private handleSelectionEnd;
    private locateClick;
    private locateDrag;
}
