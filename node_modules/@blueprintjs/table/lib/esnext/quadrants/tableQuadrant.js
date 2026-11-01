import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
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
import classNames from "classnames";
import { AbstractComponent } from "@blueprintjs/core";
import * as Classes from "../common/classes";
import * as Errors from "../common/errors";
export var QuadrantType;
(function (QuadrantType) {
    /**
     * The main quadrant beneath any frozen rows or columns.
     */
    QuadrantType["MAIN"] = "main";
    /**
     * The top quadrant, containing column headers and frozen rows.
     */
    QuadrantType["TOP"] = "top";
    /**
     * The left quadrant, containing row headers and frozen columns.
     */
    QuadrantType["LEFT"] = "left";
    /**
     * The top-left quadrant, containing the headers and cells common to both
     * the frozen columns and frozen rows.
     */
    QuadrantType["TOP_LEFT"] = "top-left";
})(QuadrantType || (QuadrantType = {}));
export class TableQuadrant extends AbstractComponent {
    // we want the user to explicitly pass a quadrantType. define defaultProps as a Partial to avoid
    // declaring that and other required props here.
    static defaultProps = {
        enableColumnHeader: true,
        enableRowHeader: true,
    };
    render() {
        const { grid, enableRowHeader, quadrantType, bodyRenderer, enableColumnHeader } = this.props;
        const showFrozenRowsOnly = quadrantType === QuadrantType.TOP || quadrantType === QuadrantType.TOP_LEFT;
        const showFrozenColumnsOnly = quadrantType === QuadrantType.LEFT || quadrantType === QuadrantType.TOP_LEFT;
        const className = classNames(Classes.TABLE_QUADRANT, this.getQuadrantCssClass(), this.props.className);
        const maybeMenu = enableRowHeader && this.props.menuRenderer?.();
        const maybeRowHeader = enableRowHeader && this.props.rowHeaderCellRenderer?.(showFrozenRowsOnly);
        const maybeColumnHeader = enableColumnHeader && this.props.columnHeaderCellRenderer?.(showFrozenColumnsOnly);
        const body = bodyRenderer(quadrantType, showFrozenRowsOnly, showFrozenColumnsOnly);
        // need to set bottom container size to prevent overlay clipping on scroll
        const bottomContainerStyle = {
            height: grid.getHeight(),
            width: grid.getWidth(),
        };
        return (_jsx("div", { className: className, style: this.props.style, ref: this.props.quadrantRef, children: _jsxs("div", { className: Classes.TABLE_QUADRANT_SCROLL_CONTAINER, ref: this.props.scrollContainerRef, onScroll: this.props.onScroll, onWheel: this.props.onWheel, children: [_jsxs("div", { className: Classes.TABLE_TOP_CONTAINER, children: [maybeMenu, maybeColumnHeader] }), _jsxs("div", { className: Classes.TABLE_BOTTOM_CONTAINER, style: bottomContainerStyle, children: [maybeRowHeader, _jsx("div", { className: Classes.TABLE_QUADRANT_BODY_CONTAINER, ref: this.props.bodyRef, children: body })] })] }) }));
    }
    validateProps(nextProps) {
        const { quadrantType } = nextProps;
        if (nextProps.onScroll != null && quadrantType != null && quadrantType !== QuadrantType.MAIN) {
            console.warn(Errors.QUADRANT_ON_SCROLL_UNNECESSARILY_DEFINED);
        }
    }
    getQuadrantCssClass() {
        switch (this.props.quadrantType) {
            case QuadrantType.MAIN:
                return Classes.TABLE_QUADRANT_MAIN;
            case QuadrantType.TOP:
                return Classes.TABLE_QUADRANT_TOP;
            case QuadrantType.LEFT:
                return Classes.TABLE_QUADRANT_LEFT;
            case QuadrantType.TOP_LEFT:
                return Classes.TABLE_QUADRANT_TOP_LEFT;
            default:
                return undefined;
        }
    }
}
//# sourceMappingURL=tableQuadrant.js.map