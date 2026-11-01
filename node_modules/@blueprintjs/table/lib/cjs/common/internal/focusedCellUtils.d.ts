import { type Region } from "../../regions";
import type { TableProps } from "../../tableProps";
import { type CellCoordinates, type FocusedCell, type FocusedCellCoordinates, type FocusedRegion, type FocusedRow, FocusMode } from "../cellTypes";
/**
 * Returns the inferred focus mode from the table props. This prefers the new focus mode API, falling back to the
 * deprecated enableFocusedCell API if that is not provided.
 */
export declare function getFocusModeFromProps(props: TableProps): FocusMode | undefined;
/**
 * Returns the inferred focused region from the table props. This prefers the new focus mode API, falling back to the
 * deprecated API if a focused region is not provided.
 */
export declare function getFocusedRegionFromProps(props: TableProps): FocusedRegion | undefined;
export declare function getFocusedCellFromCoordinates(focusedCell: FocusedCellCoordinates | undefined): FocusedCell | undefined;
/**
 * Returns the `focusedSelectionIndex` if both the focused region and that
 * property are defined, or the last index of `selectedRegions` otherwise. If
 * `selectedRegions` is empty, the function always returns `undefined`.
 */
export declare function getFocusedOrLastSelectedIndex(selectedRegions: Region[], focusedRegion?: FocusedRegion): number | undefined;
/**
 * Returns the proper focused region for the given set of initial conditions.
 */
export declare function getInitialFocusedRegion(focusMode: FocusMode | undefined, focusedRegionFromProps: FocusedRegion | undefined, focusedRegionFromState: FocusedRegion | undefined, selectedRegions: Region[]): FocusedRegion | undefined;
/**
 * Returns a focused region that matches the given focus mode if possible. If such a conversion is not possible,
 * returns undefined instead.
 */
export declare function validateFocusedRegion(focusMode: FocusMode | undefined, focusedRegion: FocusedRegion): FocusedRegion | undefined;
/**
 * Returns `true` if the focused region is located along the top boundary of the
 * provided region, or `false` otherwise.
 */
export declare function isFocusAtRegionTop(region: Region, focusedRegion: FocusedRegion): boolean;
/**
 * Returns `true` if the focused region is located along the bottom boundary of
 * the provided region, or `false` otherwise.
 */
export declare function isFocusAtRegionBottom(region: Region, focusedRegion: FocusedRegion): boolean;
/**
 * Returns `true` if the focused region is located along the left boundary of the
 * provided region, or `false` otherwise.
 */
export declare function isFocusAtRegionLeft(region: Region, focusedRegion: FocusedRegion): boolean;
/**
 * Returns `true` if the focused region is located along the right boundary of the
 * provided region, or `false` otherwise.
 */
export declare function isFocusAtRegionRight(region: Region, focusedRegion: FocusedRegion): boolean;
/**
 * Returns the column associated with this region, if there is one.
 */
export declare function getFocusedColumn(focusedRegion: FocusedRegion): number | undefined;
/**
 * Returns a new focused region object in the given focus mode that includes a focusSelectionIndex property.
 */
export declare function toFocusedRegion(focusMode: FocusMode.CELL, cellCoords: CellCoordinates, focusSelectionIndex?: number): FocusedCell;
export declare function toFocusedRegion(focusMode: FocusMode.ROW, cellCoords: CellCoordinates, focusSelectionIndex?: number): FocusedRow;
export declare function toFocusedRegion(focusMode: FocusMode | undefined, cellCoords: CellCoordinates, focusSelectionIndex?: number): FocusedRegion | undefined;
/**
 * Expands an existing region to new region based on the current focused region.
 * The focused region is an invariant and should not move as a result of this
 * operation. This function is used, for instance, to expand a selected region
 * on shift+click.
 */
export declare function expandFocusedRegion(focusedRegion: FocusedRegion, newRegion: Region): Region;
export declare function areFocusedRegionsEqual(left: FocusedRegion, right: FocusedRegion): boolean;
