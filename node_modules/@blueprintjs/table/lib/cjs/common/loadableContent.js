"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LoadableContent = void 0;
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
const core_1 = require("@blueprintjs/core");
// This class expects a single, non-string child.
class LoadableContent extends react_1.PureComponent {
    style;
    constructor(props) {
        super(props);
        this.style = this.calculateStyle(props.variableLength);
    }
    componentDidUpdate(prevProps) {
        if ((!prevProps.loading && this.props.loading) || prevProps.variableLength !== this.props.variableLength) {
            this.style = this.calculateStyle(this.props.variableLength);
        }
    }
    render() {
        if (this.props.loading) {
            return (0, jsx_runtime_1.jsx)("div", { className: core_1.Classes.SKELETON, style: this.style });
        }
        return react_1.Children.only(this.props.children);
    }
    calculateStyle(variableLength = false) {
        const skeletonLength = variableLength ? 75 - Math.floor(Math.random() * 11) * 5 : 100;
        return { width: `${skeletonLength}%` };
    }
}
exports.LoadableContent = LoadableContent;
//# sourceMappingURL=loadableContent.js.map