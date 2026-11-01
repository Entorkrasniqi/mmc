"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.GuideLayer = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2016 Palantir Technologies, Inc. All rights reserved.
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
const Classes = tslib_1.__importStar(require("../common/classes"));
class GuideLayer extends react_1.Component {
    shouldComponentUpdate(nextProps) {
        if (this.props.className !== nextProps.className) {
            return true;
        }
        // shallow-comparing guide arrays leads to tons of unnecessary re-renders, so we check the
        // array contents explicitly.
        return (!core_1.Utils.arraysEqual(this.props.verticalGuides, nextProps.verticalGuides) ||
            !core_1.Utils.arraysEqual(this.props.horizontalGuides, nextProps.horizontalGuides));
    }
    render() {
        const { verticalGuides, horizontalGuides, className } = this.props;
        const verticals = verticalGuides == null ? undefined : verticalGuides.map(this.renderVerticalGuide);
        const horizontals = horizontalGuides == null ? undefined : horizontalGuides.map(this.renderHorizontalGuide);
        return ((0, jsx_runtime_1.jsxs)("div", { className: (0, classnames_1.default)(className, Classes.TABLE_OVERLAY_LAYER), children: [verticals, horizontals] }));
    }
    renderVerticalGuide = (offset, index) => {
        const style = {
            left: `${offset}px`,
        };
        const className = (0, classnames_1.default)(Classes.TABLE_OVERLAY, Classes.TABLE_VERTICAL_GUIDE, {
            [`${Classes.TABLE_VERTICAL_GUIDE}-flush-left`]: offset === 0,
        });
        return (0, jsx_runtime_1.jsx)("div", { className: className, style: style }, index);
    };
    renderHorizontalGuide = (offset, index) => {
        const style = {
            top: `${offset}px`,
        };
        const className = (0, classnames_1.default)(Classes.TABLE_OVERLAY, Classes.TABLE_HORIZONTAL_GUIDE, {
            [`${Classes.TABLE_HORIZONTAL_GUIDE}-flush-top`]: offset === 0,
        });
        return (0, jsx_runtime_1.jsx)("div", { className: className, style: style }, index);
    };
}
exports.GuideLayer = GuideLayer;
//# sourceMappingURL=guides.js.map