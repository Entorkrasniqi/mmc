import { jsx as _jsx } from "react/jsx-runtime";
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
import classNames from "classnames";
import { PureComponent } from "react";
import * as Classes from "../common/classes";
import { Draggable } from "./draggable";
export var Orientation;
(function (Orientation) {
    Orientation[Orientation["HORIZONTAL"] = 1] = "HORIZONTAL";
    Orientation[Orientation["VERTICAL"] = 0] = "VERTICAL";
})(Orientation || (Orientation = {}));
export class ResizeHandle extends PureComponent {
    state = {
        isDragging: false,
    };
    render() {
        const { onResizeMove, onResizeEnd, onDoubleClick, orientation } = this.props;
        if (onResizeMove == null && onResizeEnd == null && onDoubleClick == null) {
            return undefined;
        }
        const targetClasses = classNames(Classes.TABLE_RESIZE_HANDLE_TARGET, {
            [Classes.TABLE_DRAGGING]: this.state.isDragging,
            [Classes.TABLE_RESIZE_HORIZONTAL]: orientation === Orientation.HORIZONTAL,
            [Classes.TABLE_RESIZE_VERTICAL]: orientation === Orientation.VERTICAL,
        }, this.props.className);
        const handleClasses = classNames(Classes.TABLE_RESIZE_HANDLE, {
            [Classes.TABLE_DRAGGING]: this.state.isDragging,
        });
        return (_jsx(Draggable, { onActivate: this.handleActivate, onClick: this.handleClick, onDoubleClick: this.handleDoubleClick, onDragEnd: this.handleDragEnd, onDragMove: this.handleDragMove, children: _jsx("div", { className: targetClasses, children: _jsx("div", { className: handleClasses }) }) }));
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
//# sourceMappingURL=resizeHandle.js.map