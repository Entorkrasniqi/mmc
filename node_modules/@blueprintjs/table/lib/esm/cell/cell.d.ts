import { Component } from "react";
import { type IntentProps, type Props } from "@blueprintjs/core";
export interface CellProps extends IntentProps, Props {
    key?: string;
    children?: React.ReactNode;
    style?: React.CSSProperties;
    /**
     * The column index of the cell. If provided, this will be passed as an argument to any callbacks
     * when they are invoked.
     */
    columnIndex?: number;
    /**
     * If `true`, the cell will be rendered above overlay layers to enable mouse
     * interactions within the cell.
     *
     * @default false
     */
    interactive?: boolean;
    /**
     * An optional native tooltip that is displayed on hover.
     * If `true`, content will be replaced with a fixed-height skeleton.
     *
     * @default false
     */
    loading?: boolean;
    /**
     * The row index of the cell. If provided, this will be passed as an argument to any callbacks
     * when they are invoked.
     */
    rowIndex?: number;
    /**
     * An optional native tooltip that is displayed on hover.
     */
    tooltip?: string;
    /**
     * If `true`, the cell contents will be wrapped in a `div` with
     * styling that will prevent the content from overflowing the cell.
     *
     * @default true
     */
    truncated?: boolean;
    /**
     * If `true`, the cell contents will be wrapped in a `div` with
     * styling that will cause text to wrap, rather than displaying it on a single line.
     *
     * @default false
     */
    wrapText?: boolean;
    /**
     * Allows for setting a tab index on the cell, so the cell can be browser-focusable.
     */
    tabIndex?: number;
    /**
     * Callback invoked when the cell is focused and a key is pressed down.
     */
    onKeyDown?: React.KeyboardEventHandler<HTMLElement>;
    /**
     * Callback invoked when the cell is focused and a key is released.
     */
    onKeyUp?: React.KeyboardEventHandler<HTMLElement>;
    /**
     * Callback invoked when a character-key is pressed.
     */
    onKeyPress?: React.KeyboardEventHandler<HTMLElement>;
    /**
     * A ref handle to capture the outer div of this cell. Used internally.
     */
    cellRef?: React.Ref<HTMLDivElement>;
}
export type CellRenderer = (rowIndex: number, columnIndex: number) => React.ReactElement<CellProps> | undefined;
export declare const emptyCellRenderer: () => import("react/jsx-runtime").JSX.Element;
/**
 * Cell component.
 *
 * @see https://blueprintjs.com/docs/#table/api.cell
 */
export declare class Cell extends Component<CellProps> {
    static displayName: string;
    static defaultProps: {
        truncated: boolean;
        wrapText: boolean;
    };
    shouldComponentUpdate(nextProps: CellProps): boolean;
    render(): import("react/jsx-runtime").JSX.Element;
}
