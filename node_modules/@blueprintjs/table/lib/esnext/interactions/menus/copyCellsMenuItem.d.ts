import { PureComponent } from "react";
import { type MenuItemProps } from "@blueprintjs/core";
import type { MenuContext } from "./menuContext";
export interface CopyCellsMenuItemProps extends Omit<MenuItemProps, "onCopy"> {
    /**
     * The menu context that launched the menu.
     */
    context: MenuContext;
    /**
     * A callback that returns the data for a specific cell. This need not
     * match the value displayed in the `<Cell>` component. The value will be
     * invisibly added as `textContent` into the DOM before copying.
     */
    getCellData: (row: number, col: number) => any;
    /**
     * If you want to do something after the copy or if you want to notify the
     * user if a copy fails, you may provide this optional callback.
     *
     * Due to browser limitations, the copy can fail. This usually occurs if
     * the selection is too large, like 20,000+ cells. The copy will also fail
     * if the browser does not support the copy method (see
     * `Clipboard.isCopySupported`).
     */
    onCopy?: (success: boolean) => void;
}
export declare class CopyCellsMenuItem extends PureComponent<CopyCellsMenuItemProps> {
    render(): import("react/jsx-runtime").JSX.Element;
    private handleClick;
}
