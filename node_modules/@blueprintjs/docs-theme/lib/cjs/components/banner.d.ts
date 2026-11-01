import { PureComponent } from "react";
import { Intent, type Props } from "@blueprintjs/core";
export interface BannerProps extends Props {
    children?: React.ReactNode;
    /** Link URL. */
    href: string;
    /**
     * Intent color of banner.
     *
     * @default Intent.PRIMARY
     */
    intent?: Intent;
}
/**
 * Render `Banner` before `Documentation` for a full-width colored banner link across the top of the page.
 * Use this to alert users to make changes or new pages.
 */
export declare class Banner extends PureComponent<BannerProps> {
    render(): import("react/jsx-runtime").JSX.Element;
}
