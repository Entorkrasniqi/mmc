import { PureComponent } from "react";
import { type FocusedCellCoordinates, type FocusedRegion, FocusMode } from "../common/cellTypes";
import { type Region } from "../regions";
import type { CoordinateData, DraggableChildrenProps } from "./dragTypes";
export type SelectedRegionTransform = (region: Region, event: MouseEvent | KeyboardEvent, coords?: CoordinateData) => Region;
export interface SelectableProps {
    /**
     * If `false`, only a single region of a single column/row/cell may be
     * selected at one time. Using `ctrl` or `meta` key will have no effect,
     * and a mouse drag will select the current column/row/cell only.
     *
     * @default false
     */
    enableMultipleSelection?: boolean;
    /**
     * The currently focused cell.
     *
     * @deprecated Use `focusedRegion` and `focusMode` instead.
     */
    focusedCell?: FocusedCellCoordinates;
    /**
     * The currently focused region.
     */
    focusedRegion?: FocusedRegion;
    /**
     * The the type shape allowed for focus areas. Can be cell, row, or none.
     */
    focusMode?: FocusMode | undefined;
    /**
     * When the user focuses something, this callback is called with new
     * focused cell coordinates. This should be considered the new focused cell
     * state for the entire table.
     *
     * @deprecated Use `onFocusedRegion` instead
     */
    onFocusedCell?: (focusedCell: FocusedCellCoordinates) => void;
    /**
     * When the user focuses something, this callback is called with new
     * focused cell coordinates. This should be considered the new focused cell
     * state for the entire table.
     */
    onFocusedRegion?: (focusedRegion: FocusedRegion) => void;
    /**
     * When the user selects something, this callback is called with a new
     * array of `Region`s. This array should be considered the new selection
     * state for the entire table.
     */
    onSelection: (regions: Region[]) => void;
    /**
     * An additional convenience callback invoked when the user releases the
     * mouse from either a click or a drag, indicating that the selection
     * interaction has ended.
     */
    onSelectionEnd?: (regions: Region[]) => void;
    /**
     * An array containing the table's selection Regions.
     *
     * @default []
     */
    selectedRegions?: Region[];
    /**
     * An optional transform function that will be applied to the located
     * `Region`.
     *
     * This allows you to, for example, convert cell `Region`s into row
     * `Region`s while maintaining the existing multi-select and meta-click
     * functionality.
     */
    selectedRegionTransform?: SelectedRegionTransform;
}
export interface DragSelectableProps extends SelectableProps, DraggableChildrenProps {
    /**
     * A list of CSS selectors that should _not_ trigger selection when a `mousedown` occurs inside of them.
     */
    ignoredSelectors?: string[];
    /**
     * Whether the selection behavior is disabled.
     *
     * @default false
     */
    disabled?: boolean | ((event: MouseEvent) => boolean);
    /**
     * A callback that determines a `Region` for the single `MouseEvent`. If
     * no valid region can be found, `null` may be returned.
     */
    locateClick: (event: MouseEvent) => Region;
    /**
     * A callback that determines a `Region` for the `MouseEvent` and
     * coordinate data representing a drag. If no valid region can be found,
     * `null` may be returned.
     */
    locateDrag: (event: MouseEvent, coords: CoordinateData, returnEndOnly?: boolean) => Region | undefined;
}
export declare class DragSelectable extends PureComponent<DragSelectableProps> {
    static defaultProps: Partial<DragSelectableProps>;
    static displayName: string;
    private get focusedCellUtils();
    private didExpandSelectionOnActivate;
    private lastEmittedSelectedRegions;
    render(): import("react/jsx-runtime").JSX.Element;
    private getDraggableHandlers;
    private handleActivate;
    private handleDragMove;
    private handleDragEnd;
    private handleClick;
    private shouldExpandSelection;
    private shouldAddDisjointSelection;
    private shouldIgnoreMouseDown;
    private handleClearSelectionAtIndex;
    private handleClearAllSelectionsNotAtIndex;
    private handleExpandSelection;
    private handleAddDisjointSelection;
    private handleReplaceSelection;
    private maybeInvokeSelectionCallback;
    private invokeOnFocusCallbackForRegion;
    private finishInteraction;
    /**
     * Expands the last-selected region to the new region, and replaces the
     * last-selected region with the expanded region. If a focused cell is provided,
     * the focused cell will serve as an anchor for the expansion.
     */
    private expandSelectedRegions;
    private getFocusedRegion;
}
