"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NavButton = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2018 Palantir Technologies, Inc. All rights reserved.
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
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const core_1 = require("@blueprintjs/core");
const NavButton = ({ icon, onClick, hotkey, text }) => ((0, jsx_runtime_1.jsxs)("div", { className: (0, classnames_1.default)("docs-nav-button", core_1.Classes.TEXT_MUTED), onClick: onClick, children: [(0, jsx_runtime_1.jsx)(core_1.Icon, { icon: icon }), (0, jsx_runtime_1.jsx)("span", { className: core_1.Classes.FILL, children: text }), (0, jsx_runtime_1.jsx)("div", { style: { opacity: 0.5 }, children: (0, jsx_runtime_1.jsx)(core_1.KeyComboTag, { combo: hotkey, minimal: true }) })] }));
exports.NavButton = NavButton;
//# sourceMappingURL=navButton.js.map