import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import classNames from "classnames";
import { Classes } from "@blueprintjs/core";
import { COMPONENT_DISPLAY_NAMESPACE } from "../common";
export const NavMenuItem = props => {
    const { className, isActive, isExpanded, section, ...htmlProps } = props;
    return (_jsxs("a", { className: classNames(Classes.MENU_ITEM, className), ...htmlProps, children: [_jsx("span", { children: section.title }), props.children] }));
};
NavMenuItem.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.NavMenuItem`;
//# sourceMappingURL=navMenuItem.js.map