"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NavMenuItem = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const core_1 = require("@blueprintjs/core");
const common_1 = require("../common");
const NavMenuItem = props => {
    const { className, isActive, isExpanded, section, ...htmlProps } = props;
    return ((0, jsx_runtime_1.jsxs)("a", { className: (0, classnames_1.default)(core_1.Classes.MENU_ITEM, className), ...htmlProps, children: [(0, jsx_runtime_1.jsx)("span", { children: section.title }), props.children] }));
};
exports.NavMenuItem = NavMenuItem;
exports.NavMenuItem.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.NavMenuItem`;
//# sourceMappingURL=navMenuItem.js.map