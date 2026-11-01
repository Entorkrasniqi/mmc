import { type HeadingNode, type PageData, type PageNode, type TsDocBase } from "@documentalist/client";
import { PureComponent } from "react";
import { type Props } from "@blueprintjs/core";
import { type DocsData } from "../common/context";
import { type TagRendererMap } from "../tags";
import type { NavMenuItemProps } from "./navMenuItem";
export interface DocumentationProps extends Props {
    /**
     * An element to place above the documentation, along the top of the viewport.
     * For best results, use a `Banner` from this package.
     */
    banner?: React.JSX.Element;
    /**
     * Default page to render in the absence of a hash route.
     */
    defaultPageId: string;
    /**
     * All the docs data from Documentalist.
     * This theme requires the Markdown plugin, and optionally supports Typescript and KSS data.
     */
    docs: DocsData;
    /**
     * Elements to render on the bottom of the sidebar, below the nav menu.
     * This typically contains copyright information.
     */
    footer?: React.ReactNode;
    /**
     * Elements to render on the top of the sidebar, above the search box.
     * This typically contains logo, title and navigation links.
     * Use `.docs-nav-title` on an element for proper padding relative to other sidebar elements.
     */
    header: React.ReactNode;
    /**
     * Callback invoked to determine if given nav node should *not* be
     * searchable in the navigator. Returning `true` will exclude the item from
     * the navigator search results.
     */
    navigatorExclude?: (node: PageNode | HeadingNode) => boolean;
    /**
     * Callback invoked whenever the component props or state change (specifically,
     * called in `componentDidMount` and `componentDidUpdate`).
     * Use it to run non-React code on the newly rendered sections.
     */
    onComponentUpdate?: (pageId: string) => void;
    /**
     * Callback invoked to render "View source" links in Typescript interfaces.
     * The `href` of the link will be `entry.sourceUrl`.
     *
     * @default "View source"
     */
    renderViewSourceLinkText?: (entry: TsDocBase) => React.ReactNode;
    /**
     * Callback invoked to render the clickable nav menu items. (Nested menu structure is handled by the library.)
     * The default implementation renders a `NavMenuItem` element, which is exported from this package.
     */
    renderNavMenuItem?: (props: NavMenuItemProps) => React.JSX.Element;
    /**
     * Callback invoked to render actions for a documentation page.
     * Actions appear in an element in the upper-right corner of the page.
     */
    renderPageActions?: (page: PageData) => React.ReactNode;
    /**
     * HTML element to use as the scroll parent. By default `document.documentElement` is assumed to be the scroll container.
     *
     * @default document.documentElement
     */
    scrollParent?: HTMLElement;
    /** Tag renderer functions. Unknown tags will log console errors. */
    tagRenderers: TagRendererMap;
}
export interface DocumentationState {
    activeApiMember: string;
    activePageId: string;
    activeSectionId: string;
    isApiBrowserOpen: boolean;
    isNavigatorOpen: boolean;
}
export declare class Documentation extends PureComponent<DocumentationProps, DocumentationState> {
    /** Map of section route to containing page reference. */
    private routeToPage;
    private contentElement;
    private navElement;
    private refHandlers;
    constructor(props: DocumentationProps);
    render(): import("react/jsx-runtime").JSX.Element;
    componentDidMount(): void;
    componentWillUnmount(): void;
    componentDidUpdate(_prevProps: DocumentationProps, prevState: DocumentationState): void;
    private getDocumentationContextApi;
    private updateHash;
    private handleHashChange;
    private handleCloseNavigator;
    private handleOpenNavigator;
    private handleNavigation;
    private handleNextSection;
    private handlePreviousSection;
    private handleScroll;
    private maybeScrollToActivePageMenuItem;
    private scrollToActiveSection;
    private shiftSection;
    private handleApiBrowserOpen;
    private handleApiBrowserClose;
}
