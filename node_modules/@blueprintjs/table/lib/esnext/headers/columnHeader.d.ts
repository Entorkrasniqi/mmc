import { Component } from "react";
import type { ColumnIndices } from "../common/grid";
import type { IndexedResizeCallback } from "../interactions/resizable";
import { type ColumnHeaderCellProps } from "./columnHeaderCell";
import { type HeaderProps } from "./header";
export type ColumnHeaderRenderer = (columnIndex: number) => React.ReactElement<ColumnHeaderCellProps> | null;
export interface ColumnWidths {
    minColumnWidth: number;
    maxColumnWidth: number;
    defaultColumnWidth: number;
}
export interface ColumnHeaderProps extends React.PropsWithChildren<HeaderProps>, ColumnWidths, ColumnIndices {
    /**
     * A ColumnHeaderRenderer that, for each `<Column>`, will delegate to:
     * 1. The `columnHeaderCellRenderer` method from the `<Column>`
     * 2. A `<ColumnHeaderCell>` using the `name` prop from the `<Column>`
     * 3. A `<ColumnHeaderCell>` with a `name` generated from `Utils.toBase26Alpha`
     */
    cellRenderer: ColumnHeaderRenderer;
    /**
     * Ref handler that receives the HTML element that should be measured to
     * indicate the fluid height of the column header.
     */
    measurableElementRef?: React.Ref<HTMLDivElement>;
    /**
     * A callback invoked when user is done resizing the column
     */
    onColumnWidthChanged: IndexedResizeCallback;
    /**
     * Called on component mount.
     */
    onMount?: (whichHeader: "column" | "row") => void;
}
export declare class ColumnHeader extends Component<ColumnHeaderProps> {
    static defaultProps: {
        isReorderable: boolean;
        isResizable: boolean;
        loading: boolean;
    };
    componentDidMount(): void;
    render(): import("react/jsx-runtime").JSX.Element;
    private wrapCells;
    private convertPointToColumn;
    private getCellExtremaClasses;
    private getColumnWidth;
    private getDragCoordinate;
    private getMouseCoordinate;
    private handleResizeEnd;
    private handleResizeDoubleClick;
    private handleSizeChanged;
    private isCellSelected;
    private isGhostIndex;
    private renderGhostCell;
    private toRegion;
}
