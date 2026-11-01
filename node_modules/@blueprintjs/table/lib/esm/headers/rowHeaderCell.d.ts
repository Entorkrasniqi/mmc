import { AbstractPureComponent, type Props } from "@blueprintjs/core";
import { type HeaderCellProps } from "./headerCell";
export interface RowHeaderCellProps extends HeaderCellProps, Props {
    /**
     * Specifies if the row is reorderable.
     */
    enableRowReordering?: boolean;
    /**
     * Specifies whether the full row is part of a selection.
     */
    isRowSelected?: boolean;
    /**
     * A callback to override the default name rendering behavior. The default
     * behavior is to simply use the `RowHeaderCell`s name prop.
     *
     * This render callback can be used, for example, to provide a
     * `EditableName` component for editing row names.
     *
     * The callback will also receive the row index if an `index` was originally
     * provided via props.
     */
    nameRenderer?: (name: string, index?: number) => React.ReactElement<Props>;
}
export declare class RowHeaderCell extends AbstractPureComponent<RowHeaderCellProps> {
    render(): import("react/jsx-runtime").JSX.Element;
}
