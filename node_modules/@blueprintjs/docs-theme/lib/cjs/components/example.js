"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Example = void 0;
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
const react_1 = require("react");
/**
 * Container for an example and its options.
 *
 * ```tsx
 * import { PureComponent } from "react";
 *
 * import { Example, ExampleProps } from "@blueprintjs/docs-theme";
 *
 * // use ExampleProps as your props type,
 * // then spread it to <Example> below
 * export class MyExample extends PureComponent<ExampleProps, [your state]> {
 *     public render() {
 *         const options = (
 *             <>
 *                  --- render options here ---
 *             </>
 *         );
 *         return (
 *             <Example options={options} {...this.props}>
 *                 --- render examples here ---
 *             </Example>
 *         );
 *     }
 * ```
 */
class Example extends react_1.PureComponent {
    static defaultProps = {
        forceUpdate: true,
        showOptionsBelowExample: false,
    };
    hasDelayedInitialRender = false;
    render() {
        const { children, className, data, forceUpdate, html, id, options, showOptionsBelowExample, 
        // spread any additional props through to the root element,
        // to support decorators that expect DOM props.
        ...htmlProps } = this.props;
        // `forceUpdate` -  Don't let any React nodes into the DOM until the
        // `requestAnimationFrame` delay has elapsed.
        if (forceUpdate && !this.hasDelayedInitialRender) {
            return null;
        }
        const classes = (0, classnames_1.default)("docs-example-frame", showOptionsBelowExample ? "docs-example-frame-column" : "docs-example-frame-row", className);
        const example = html == null ? ((0, jsx_runtime_1.jsx)("div", { className: "docs-example", children: children })) : ((0, jsx_runtime_1.jsx)("div", { className: "docs-example", dangerouslySetInnerHTML: { __html: html } }));
        return ((0, jsx_runtime_1.jsxs)("div", { className: classes, "data-example-id": id, ...htmlProps, children: [example, options && (0, jsx_runtime_1.jsx)("div", { className: "docs-example-options", children: options })] }));
    }
    componentDidMount() {
        // `forceUpdate` - The docs app suffers from a Flash of Unstyled Content
        // that causes components to mis-measure themselves on first render.
        // Delay initial render till the DOM loads with a requestAnimationFrame.
        if (this.props.forceUpdate) {
            requestAnimationFrame(() => {
                this.hasDelayedInitialRender = true;
                this.forceUpdate();
            });
        }
    }
}
exports.Example = Example;
//# sourceMappingURL=example.js.map