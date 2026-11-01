import { jsx as _jsx } from "react/jsx-runtime";
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
import classNames from "classnames";
import { Component } from "react";
import { ContextMenu, Classes as CoreClasses, Utils as CoreUtils } from "@blueprintjs/core";
import * as Classes from "../common/classes";
export class HeaderCell extends Component {
    state = {
        isActive: false,
    };
    shouldComponentUpdate(nextProps) {
        return (!CoreUtils.shallowCompareKeys(this.props, nextProps, { exclude: ["style"] }) ||
            !CoreUtils.deepCompareKeys(this.props, nextProps, ["style"]));
    }
    render() {
        const classes = classNames(Classes.TABLE_HEADER, {
            [Classes.TABLE_HEADER_ACTIVE]: this.props.isActive || this.state.isActive,
            [Classes.TABLE_HEADER_SELECTED]: this.props.isSelected,
            [CoreClasses.LOADING]: this.props.loading,
        }, this.props.className);
        const hasMenu = this.props.menuRenderer !== undefined;
        return (_jsx(ContextMenu, { className: classes, content: this.props.menuRenderer?.(this.props.index), disabled: !hasMenu, style: this.props.style, ref: this.props.targetRef, children: this.props.children }));
    }
}
//# sourceMappingURL=headerCell.js.map