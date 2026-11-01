import { Component } from "react";
import { type Props } from "@blueprintjs/core";
import type { QuadrantType } from "../quadrants/tableQuadrant";
import { type Region } from "../regions";
export type RegionStyler = (region: Region, quadrantType?: QuadrantType) => React.CSSProperties;
export interface RegionLayerProps extends Props {
    /**
     * The array of regions to render.
     */
    regions?: Region[];
    /**
     * The array of CSS styles to apply to each region. The ith style object in this array will be
     * applied to the ith region in `regions`.
     */
    regionStyles?: React.CSSProperties[];
}
export declare class RegionLayer extends Component<RegionLayerProps> {
    shouldComponentUpdate(nextProps: RegionLayerProps): boolean;
    render(): import("react/jsx-runtime").JSX.Element;
    private renderRegionChildren;
    private renderRegion;
}
