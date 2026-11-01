"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NavMenu = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
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
const client_1 = require("@documentalist/client");
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const core_1 = require("@blueprintjs/core");
const common_1 = require("../common");
const navMenuItem_1 = require("./navMenuItem");
const NavMenu = props => {
    const { renderNavMenuItem = navMenuItem_1.NavMenuItem } = props;
    const menu = props.items.map(section => {
        const isActive = props.activeSectionId === section.route;
        const isExpanded = isActive || isParentOfRoute(section.route, props.activeSectionId);
        // active section gets selected styles, expanded section shows its children
        const itemClasses = (0, classnames_1.default)(`depth-${section.level - props.level - 1}`, {
            "docs-nav-expanded": isExpanded,
            [core_1.Classes.ACTIVE]: isActive,
        });
        const item = renderNavMenuItem({
            className: itemClasses,
            href: "#" + section.route,
            isActive,
            isExpanded,
            onClick: () => props.onItemClick(section.route),
            section,
        });
        return ((0, jsx_runtime_1.jsxs)("li", { children: [item, (0, client_1.isPageNode)(section) ? (0, jsx_runtime_1.jsx)(exports.NavMenu, { ...props, level: section.level, items: section.children }) : null] }, section.route));
    });
    const classes = (0, classnames_1.default)("docs-nav-menu", core_1.Classes.LIST_UNSTYLED, props.className);
    return (0, jsx_runtime_1.jsx)("ul", { className: classes, children: menu });
};
exports.NavMenu = NavMenu;
exports.NavMenu.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.NavMenu`;
function isParentOfRoute(parent, route) {
    return route.indexOf(parent + "/") === 0 || route.indexOf(parent + ".") === 0;
}
//# sourceMappingURL=navMenu.js.map