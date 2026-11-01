"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ResizeHandle = exports.Orientation = void 0;
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
const Classes = tslib_1.__importStar(require("../common/classes"));
const draggable_1 = require("./draggable");
var Orientation;
(function (Orientation) {
    Orientation[Orientation["HORIZONTAL"] = 1] = "HORIZONTAL";
    Orientation[Orientation["VERTICAL"] = 0] = "VERTICAL";
})(Orientation || (exports.Orientation = Orientation = {}));
class ResizeHandle extends react_1.PureComponent {
    state = {
        isDragging: false,
    };
    render() {
        const { onResizeMove, onResizeEnd, onDoubleClick, orientation } = this.props;
        if (onResizeMove == null && onResizeEnd == null && onDoubleClick == null) {
            return undefined;
        }
        const targetClasses = (0, classnames_1.default)(Classes.TABLE_RESIZE_HANDLE_TARGET, {
            [Classes.TABLE_DRAGGING]: this.state.isDragging,
            [Classes.TABLE_RESIZE_HORIZONTAL]: orientation === Orientation.HORIZONTAL,
            [Classes.TABLE_RESIZE_VERTICAL]: orientation === Orientation.VERTICAL,
        }, this.props.className);
        const handleClasses = (0, classnames_1.default)(Classes.TABLE_RESIZE_HANDLE, {
            [Classes.TABLE_DRAGGING]: this.state.isDragging,
        });
        return ((0, jsx_runtime_1.jsx)(draggable_1.Draggable, { onActivate: this.handleActivate, onClick: this.handleClick, onDoubleClick: this.handleDoubleClick, onDragEnd: this.handleDragEnd, onDragMove: this.handleDragMove, children: (0, jsx_runtime_1.jsx)("div", { className: targetClasses, children: (0, jsx_runtime_1.jsx)("div", { className: handleClasses }) }) }));
    }
    handleActivate = (event) => {
        this.setState({ isDragging: true });
        this.props.onLayoutLock(true);
        event.stopPropagation();
        event.stopImmediatePropagation();
        return true;
    };
    handleDragMove = (_event, coords) => {
        const orientationIndex = this.props.orientation;
        if (this.props.onResizeMove != null) {
            this.props.onResizeMove(coords.offset[orientationIndex], coords.delta[orientationIndex]);
        }
    };
    handleDragEnd = (_event, coords) => {
        const orientationIndex = this.props.orientation;
        this.setState({ isDragging: false });
        this.props.onLayoutLock(false);
        if (this.props.onResizeMove != null) {
            this.props.onResizeMove(coords.offset[orientationIndex], coords.delta[orientationIndex]);
        }
        if (this.props.onResizeEnd != null) {
            this.props.onResizeEnd(coords.offset[orientationIndex]);
        }
    };
    handleClick = (_event) => {
        this.setState({ isDragging: false });
        this.props.onLayoutLock(false);
    };
    handleDoubleClick = (_event) => {
        this.setState({ isDragging: false });
        this.props.onLayoutLock(false);
        if (this.props.onDoubleClick != null) {
            this.props.onDoubleClick();
        }
    };
}
exports.ResizeHandle = ResizeHandle;
//# sourceMappingURL=resizeHandle.js.map