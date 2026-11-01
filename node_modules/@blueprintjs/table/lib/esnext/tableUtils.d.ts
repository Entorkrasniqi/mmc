import { type ReactElement } from "react";
import type { HotkeyConfig } from "@blueprintjs/core";
import type { ColumnProps } from "./column";
import { RegionCardinality } from "./regions";
import type { TableHotkeys } from "./tableHotkeys";
import type { TablePropsWithDefaults } from "./tableProps";
export declare function clampNumFrozenColumns(props: TablePropsWithDefaults): number;
export declare function clampNumFrozenRows(props: TablePropsWithDefaults): number;
export declare function hasLoadingOption(loadingOptions: string[] | undefined, loadingOption: string): boolean;
export declare function isSelectionModeEnabled(props: TablePropsWithDefaults, selectionMode: RegionCardinality, selectionModes?: RegionCardinality[]): boolean;
export declare function getHotkeysFromProps(props: TablePropsWithDefaults, hotkeysImpl: TableHotkeys): HotkeyConfig[];
/**
 * @returns true if new and old children arrays are the same
 */
export declare function compareChildren(newChildren: Array<ReactElement<ColumnProps>>, oldChildren: Array<ReactElement<ColumnProps>>): boolean;
