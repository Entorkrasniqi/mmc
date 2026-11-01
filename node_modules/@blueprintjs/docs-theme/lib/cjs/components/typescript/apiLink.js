"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApiLink = void 0;
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
const react_1 = require("react");
const common_1 = require("../../common");
const context_1 = require("../../common/context");
/**
 * Renders a link to open a symbol in the API Browser.
 */
const ApiLink = ({ className, name }) => {
    const { showApiDocs } = (0, react_1.useContext)(context_1.DocumentationContext);
    const handleClick = (0, react_1.useCallback)((evt) => {
        evt.preventDefault();
        showApiDocs(name);
    }, [name, showApiDocs]);
    return ((0, jsx_runtime_1.jsx)("a", { className: className, href: `#api/${name}`, onClick: handleClick, children: name }));
};
exports.ApiLink = ApiLink;
exports.ApiLink.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.ApiLink`;
//# sourceMappingURL=apiLink.js.map