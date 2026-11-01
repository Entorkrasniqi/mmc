"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Banner = void 0;
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
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
/**
 * Render `Banner` before `Documentation` for a full-width colored banner link across the top of the page.
 * Use this to alert users to make changes or new pages.
 */
class Banner extends react_1.PureComponent {
    render() {
        const { children, className, href, intent = core_1.Intent.PRIMARY } = this.props;
        const classes = (0, classnames_1.default)("docs-banner", core_1.Classes.intentClass(intent), className);
        return ((0, jsx_runtime_1.jsx)("div", { className: classes, role: "banner", children: (0, jsx_runtime_1.jsx)("a", { href: href, target: "_blank", children: children }) }));
    }
}
exports.Banner = Banner;
//# sourceMappingURL=banner.js.map