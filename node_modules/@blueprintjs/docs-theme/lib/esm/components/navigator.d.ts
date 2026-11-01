import type { HeadingNode, PageNode } from "@documentalist/client";
import { PureComponent } from "react";
export interface NavigatorProps {
    /** Whether navigator is open. */
    isOpen: boolean;
    /** All potentially navigable items. */
    items: Array<PageNode | HeadingNode>;
    /** Callback to determine if a given item should be excluded. */
    itemExclude?: (node: PageNode | HeadingNode) => boolean;
    /**
     * Callback invoked when the navigator is closed. Navigation is performed by
     * updating browser `location` directly.
     */
    onClose: () => void;
    /**
     * Whether to use dark theme.
     */
    useDarkTheme?: boolean;
}
export interface NavigationSection {
    path: string[];
    route: string;
    title: string;
}
export declare class Navigator extends PureComponent<NavigatorProps> {
    private sections;
    componentDidMount(): void;
    render(): import("react/jsx-runtime").JSX.Element | null;
    private filterMatches;
    private renderItem;
    private handleItemSelect;
}
