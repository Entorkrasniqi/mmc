import { Component } from "react";
import { type Props } from "@blueprintjs/core";
export interface GuideLayerProps extends Props {
    /**
     *  The left-offset location of the vertical guides
     */
    verticalGuides: number[];
    /**
     *  The top-offset location of the horizontal guides
     */
    horizontalGuides: number[];
}
export declare class GuideLayer extends Component<GuideLayerProps> {
    shouldComponentUpdate(nextProps: GuideLayerProps): boolean;
    render(): import("react/jsx-runtime").JSX.Element;
    private renderVerticalGuide;
    private renderHorizontalGuide;
}
