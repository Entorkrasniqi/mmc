"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DeprecatedTag = void 0;
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
const core_1 = require("@blueprintjs/core");
const common_1 = require("../../common");
const DeprecatedTag = ({ isDeprecated }) => {
    if (isDeprecated === true || typeof isDeprecated === "string") {
        return ((0, jsx_runtime_1.jsx)(core_1.Tag, { intent: core_1.Intent.DANGER, minimal: true, children: typeof isDeprecated === "string" ? ((0, jsx_runtime_1.jsx)("span", { dangerouslySetInnerHTML: markdownCode(`Deprecated: ${isDeprecated}`) })) : ("Deprecated") }));
    }
    return null;
};
exports.DeprecatedTag = DeprecatedTag;
exports.DeprecatedTag.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.DeprecatedTag`;
/**
 * Minimal markdown renderer that supports only backtick `code` elements and triple-backtick `pre` elements.
 * Does not provide any syntax highlighting.
 */
function markdownCode(text) {
    return {
        __html: text
            .replace("<", "&lt;")
            .replace(/```([^`]+)```/g, (_, code) => `<pre>${code}</pre>`)
            .replace(/`([^`]+)`/g, (_, code) => `<code>${code}</code>`),
    };
}
//# sourceMappingURL=deprecatedTag.js.map