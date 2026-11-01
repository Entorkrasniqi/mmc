"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.HeaderCell = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2022 Palantir Technologies, Inc. All rights reserved.
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
class HeaderCell extends react_1.Component {
    state = {
        isActive: false,
    };
    shouldComponentUpdate(nextProps) {
        return (!core_1.Utils.shallowCompareKeys(this.props, nextProps, { exclude: ["style"] }) ||
            !core_1.Utils.deepCompareKeys(this.props, nextProps, ["style"]));
    }
    render() {
        const classes = (0, classnames_1.default)(Classes.TABLE_HEADER, {
            [Classes.TABLE_HEADER_ACTIVE]: this.props.isActive || this.state.isActive,
            [Classes.TABLE_HEADER_SELECTED]: this.props.isSelected,
            [core_1.Classes.LOADING]: this.props.loading,
        }, this.props.className);
        const hasMenu = this.props.menuRenderer !== undefined;
        return ((0, jsx_runtime_1.jsx)(core_1.ContextMenu, { className: classes, content: this.props.menuRenderer?.(this.props.index), disabled: !hasMenu, style: this.props.style, ref: this.props.targetRef, children: this.props.children }));
    }
}
exports.HeaderCell = HeaderCell;
//# sourceMappingURL=headerCell.js.map