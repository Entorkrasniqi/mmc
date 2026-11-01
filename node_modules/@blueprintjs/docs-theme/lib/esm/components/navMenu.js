import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/*
 * Copyright 2017 Palantir Technologies, Inc. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { isPageNode } from "@documentalist/client";
import classNames from "classnames";
import { Classes } from "@blueprintjs/core";
import { COMPONENT_DISPLAY_NAMESPACE } from "../common";
import { NavMenuItem } from "./navMenuItem";
export const NavMenu = props => {
    const { renderNavMenuItem = NavMenuItem } = props;
    const menu = props.items.map(section => {
        const isActive = props.activeSectionId === section.route;
        const isExpanded = isActive || isParentOfRoute(section.route, props.activeSectionId);
        // active section gets selected styles, expanded section shows its children
        const itemClasses = classNames(`depth-${section.level - props.level - 1}`, {
            "docs-nav-expanded": isExpanded,
            [Classes.ACTIVE]: isActive,
        });
        const item = renderNavMenuItem({
            className: itemClasses,
            href: "#" + section.route,
            isActive,
            isExpanded,
            onClick: () => props.onItemClick(section.route),
            section,
        });
        return (_jsxs("li", { children: [item, isPageNode(section) ? _jsx(NavMenu, { ...props, level: section.level, items: section.children }) : null] }, section.route));
    });
    const classes = classNames("docs-nav-menu", Classes.LIST_UNSTYLED, props.className);
    return _jsx("ul", { className: classes, children: menu });
};
NavMenu.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.NavMenu`;
function isParentOfRoute(parent, route) {
    return route.indexOf(parent + "/") === 0 || route.indexOf(parent + ".") === 0;
}
//# sourceMappingURL=navMenu.js.map