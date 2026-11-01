import { PureComponent } from "react";
import type { FocusedRegion, FocusMode } from "../common/cellTypes";
import { type Region } from "../regions";
import type { CoordinateData, DraggableChildrenProps } from "./dragTypes";
export interface ReorderableProps {
    /**
     * The selected focus mode for this component. If undefined, focus is
     * disabled. This is used to determine how the focus updates upon
     * reordering.
     */
    focusMode: FocusMode | undefined;
    /**
     * A callback that is called while the user is dragging to reorder.
     *
     * @param oldIndex the original index of the element or set of elements
     * @param newIndex the new index of the element or set of elements
     * @param length the number of contiguous elements that were moved
     */
    onReordering: (oldIndex: number, newIndex: number, length: number) => void;
    /**
     * A callback that is called when the user is done dragging to reorder.
     *
     * @param oldIndex the original index of the element or set of elements
     * @param newIndex the new index of the element or set of elements
     * @param length the number of contiguous elements that were moved
     */
    onReordered: (oldIndex: number, newIndex: number, length: number) => void;
    /**
     * When the user reorders something, this callback is called with a new
     * array of `Region`s. This array should be considered the new selection
     * state for the entire table.
     */
    onSelection: (regions: Region[]) => void;
    /**
     * When the user reorders something, this callback is called with the new
     * focus region for the newly selected set of regions.
     */
    onFocusedRegion: (focusedRegion: FocusedRegion) => void;
    /**
     * An array containing the table's selection Regions.
     *
     * @default []
     */
    selectedRegions?: Region[];
}
export interface DragReorderableProps extends ReorderableProps, DraggableChildrenProps {
    /**
     * Whether the reordering behavior is disabled.
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
     * A callback that determines the index at which to show the preview guide.
     * This is equivalent to the absolute index in the old ordering where the
     * reordered element will move.
     */
    locateDrag: (event: MouseEvent, coords: CoordinateData) => number | undefined;
    /**
     * A callback that converts the provided index into a region. The returned
     * region will be used to update the current selection after drag-reordering.
     */
    toRegion: (index1: number, index2?: number) => Region;
}
export declare class DragReorderable extends PureComponent<DragReorderableProps> {
    static defaultProps: Partial<DragReorderableProps>;
    private selectedRegionStartIndex?;
    private selectedRegionLength;
    render(): import("react/jsx-runtime").JSX.Element;
    private getDraggableHandlers;
    private handleActivate;
    private handleDragMove;
    private handleDragEnd;
    private shouldIgnoreMouseDown;
    private maybeSelectRegion;
}
