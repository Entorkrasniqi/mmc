import { AbstractPureComponent, type IconName, type OverlayLifecycleProps, type PopoverProps, type Props } from "@blueprintjs/core";
import { type HeaderCellProps } from "./headerCell";
export interface ColumnNameProps {
    /**
     * The name displayed in the header of the column.
     */
    name?: string;
    /**
     * A callback to override the default name rendering behavior. The default
     * behavior is to simply use the `ColumnHeaderCell`s name prop.
     *
     * This render callback can be used, for example, to provide a
     * `EditableName` component for editing column names.
     *
     * If you define this callback, we recommend you also set
     * `<Table enableColumnInteractionBar={true}>` to avoid issues with menus or selection.
     *
     * The callback will also receive the column index if an `index` was originally
     * provided via props.
     */
    nameRenderer?: (name: string, index?: number) => React.ReactElement<Props>;
}
export interface ColumnHeaderCellProps extends HeaderCellProps, ColumnNameProps {
    /**
     * If `true`, adds an interaction bar on top of all column header cells, and
     * moves interaction triggers into it.
     *
     * @default false
     */
    enableColumnInteractionBar?: boolean;
    /**
     * Specifies if the column is reorderable.
     */
    enableColumnReordering?: boolean;
    /**
     * Specifies if the full column is part of a selection.
     */
    isColumnSelected?: boolean;
    /**
     * The icon name or element for the header's menu button.
     *
     * @default "chevron-down"
     */
    menuIcon?: IconName | React.JSX.Element;
    /**
     * Optional props to forward to the dropdown menu popover.
     * This has no effect if `menuRenderer` is undefined.
     */
    menuPopoverProps?: Omit<PopoverProps, "content" | keyof OverlayLifecycleProps>;
    /**
     * If `true`, clicks on the header menu target element will cause the column's
     * cells to be selected.
     *
     * @default true
     */
    selectCellsOnMenuClick?: boolean;
}
export interface ColumnHeaderCellState {
    isActive?: boolean;
}
/**
 * Column header cell component.
 *
 * @see https://blueprintjs.com/docs/#table/api.columnheadercell
 */
export declare class ColumnHeaderCell extends AbstractPureComponent<ColumnHeaderCellProps, ColumnHeaderCellState> {
    static displayName: string;
    static defaultProps: ColumnHeaderCellProps;
    /**
     * This method determines if a `MouseEvent` was triggered on a target that
     * should be used as the header click/drag target. This enables users of
     * this component to render fully interactive components in their header
     * cells without worry of selection or resize operations from capturing
     * their mouse events.
     */
    static isHeaderMouseTarget(target: HTMLElement): boolean;
    state: {
        isActive: boolean;
    };
    render(): import("react/jsx-runtime").JSX.Element;
    private renderName;
    private maybeRenderContent;
    private maybeRenderDropdownMenu;
    private handlePopoverOpened;
    private handlePopoverClosing;
}
