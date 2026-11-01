import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import classNames from "classnames";
import { Classes, Icon, KeyComboTag } from "@blueprintjs/core";
export const NavButton = ({ icon, onClick, hotkey, text }) => (_jsxs("div", { className: classNames("docs-nav-button", Classes.TEXT_MUTED), onClick: onClick, children: [_jsx(Icon, { icon: icon }), _jsx("span", { className: Classes.FILL, children: text }), _jsx("div", { style: { opacity: 0.5 }, children: _jsx(KeyComboTag, { combo: hotkey, minimal: true }) })] }));
//# sourceMappingURL=navButton.js.map