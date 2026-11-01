import { Component } from "react";
import { type TruncatedFormatProps } from "./truncatedFormat";
export interface JSONFormatProps extends TruncatedFormatProps {
    children?: any;
    /**
     * By default, we omit stringifying native JavaScript strings since
     * `JSON.stringify` awkwardly adds double-quotes to the display value.
     * This behavior can be turned off by setting this boolean to `false`.
     *
     * @default true
     */
    omitQuotesOnStrings?: boolean;
    /**
     * Optionally specify the stringify method. Default is `JSON.stringify`
     * with 2-space indentation.
     */
    stringify?: (obj: any) => string;
}
/**
 * JSON cell format component.
 *
 * @see https://blueprintjs.com/docs/#table/api.jsonformat
 */
export declare class JSONFormat extends Component<JSONFormatProps> {
    static displayName: string;
    static defaultProps: JSONFormatProps;
    render(): import("react/jsx-runtime").JSX.Element;
}
