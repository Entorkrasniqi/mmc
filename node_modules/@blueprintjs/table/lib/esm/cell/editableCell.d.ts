import { Component } from "react";
import { type EditableTextProps } from "@blueprintjs/core";
import { type CellProps } from "./cell";
export interface EditableCellProps extends Omit<CellProps, "onKeyDown" | "onKeyUp"> {
    /**
     * Whether the given cell is the current active/focused cell.
     */
    isFocused?: boolean;
    /**
     * The value displayed in the text box. Be sure to update this value when
     * rendering this component after a confirmed change.
     */
    value?: string;
    /**
     * A listener that is triggered if the user cancels the edit. This is
     * important to listen to if you are doing anything with `onChange` events,
     * since you'll likely want to revert whatever changes you made. The
     * callback will also receive the row index and column index if they were
     * originally provided via props.
     */
    onCancel?: (value: string, rowIndex?: number, columnIndex?: number) => void;
    /**
     * A listener that is triggered as soon as the editable name is modified.
     * This can be due, for example, to keyboard input or the clipboard. The
     * callback will also receive the row index and column index if they were
     * originally provided via props.
     */
    onChange?: (value: string, rowIndex?: number, columnIndex?: number) => void;
    /**
     * A listener that is triggered once the editing is confirmed. This is
     * usually due to the <code>return</code> (or <code>enter</code>) key press.
     * The callback will also receive the row index and column index if they
     * were originally provided via props.
     */
    onConfirm?: (value: string, rowIndex?: number, columnIndex?: number) => void;
    /**
     * Props that should be passed to the EditableText when it is used to edit
     */
    editableTextProps?: Omit<EditableTextProps, "elementRef">;
}
export interface EditableCellState {
    isEditing?: boolean;
    savedValue?: string;
    dirtyValue?: string;
}
/**
 * Editable cell component.
 *
 * @see https://blueprintjs.com/docs/#table/api.editablecell
 */
export declare class EditableCell extends Component<EditableCellProps, EditableCellState> {
    static displayName: string;
    static defaultProps: {
        truncated: boolean;
        wrapText: boolean;
    };
    private cellRef;
    private contentsRef;
    state: EditableCellState;
    componentDidMount(): void;
    componentDidUpdate(prevProps: EditableCellProps): void;
    shouldComponentUpdate(nextProps: EditableCellProps, nextState: EditableCellState): boolean;
    render(): import("react/jsx-runtime").JSX.Element;
    private renderCell;
    private checkShouldFocus;
    private handleKeyPress;
    private handleEdit;
    private handleCancel;
    private handleChange;
    private handleConfirm;
    private invokeCallback;
    private handleCellActivate;
    private handleCellDoubleClick;
    private hotkeys;
}
/** @deprecated Use `EditableCell` instead */
export declare const EditableCell2: typeof EditableCell;
export type EditableCell2 = InstanceType<typeof EditableCell2>;
/** @deprecated Use `EditableCellProps` instead */
export type EditableCell2Props = EditableCellProps;
