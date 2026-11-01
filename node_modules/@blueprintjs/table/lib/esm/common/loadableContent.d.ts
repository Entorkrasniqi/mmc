import { PureComponent } from "react";
export interface LoadableContentProps {
    children?: React.ReactNode;
    /**
     * If true, render a skeleton. Otherwise render the single, non-string child passed to this
     * component.
     */
    loading: boolean;
    /**
     * If true, show a skeleton of random width (25-75% cell width) when rendering the loading state.
     *
     * @default false
     */
    variableLength?: boolean;
}
export declare class LoadableContent extends PureComponent<LoadableContentProps> {
    private style;
    constructor(props: LoadableContentProps);
    componentDidUpdate(prevProps: LoadableContentProps): void;
    render(): string | number | boolean | Iterable<import("react").ReactNode> | import("react/jsx-runtime").JSX.Element | null | undefined;
    private calculateStyle;
}
