import { Component } from "react";
import type { RowIndices } from "../common/grid";
import type { IndexedResizeCallback } from "../interactions/resizable";
import { type HeaderProps } from "./header";
import { type RowHeaderCellProps } from "./rowHeaderCell";
export type RowHeaderRenderer = (rowIndex: number) => React.ReactElement<RowHeaderCellProps>;
export interface RowHeights {
    minRowHeight: number;
    maxRowHeight: number;
    defaultRowHeight: number;
}
export interface RowHeaderProps extends HeaderProps, RowHeights, RowIndices {
    /**
     * A callback invoked when user is done resizing the column
     */
    onRowHeightChanged: IndexedResizeCallback;
    /**
     * Renders the cell for each row header
     */
    rowHeaderCellRenderer?: RowHeaderRenderer;
    /**
     * Called on component mount.
     */
    onMount?: (whichHeader: "column" | "row") => void;
}
export declare class RowHeader extends Component<RowHeaderProps> {
    static defaultProps: {
        rowHeaderCellRenderer: typeof renderDefaultRowHeader;
    };
    componentDidMount(): void;
    render(): import("react/jsx-runtime").JSX.Element;
    private wrapCells;
    private convertPointToRow;
    private getCellExtremaClasses;
    private getRowHeight;
    private getDragCoordinate;
    private getMouseCoordinate;
    private handleResizeEnd;
    private handleSizeChanged;
    private isCellSelected;
    private isGhostIndex;
    private renderGhostCell;
    private toRegion;
}
/**
 * A default implementation of `RowHeaderRenderer` that displays 1-indexed
 * numbers for each row.
 */
export declare function renderDefaultRowHeader(rowIndex: number): import("react/jsx-runtime").JSX.Element;
