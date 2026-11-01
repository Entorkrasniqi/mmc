"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Resizable = void 0;
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
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const index_1 = require("../common/index");
const resizeHandle_1 = require("./resizeHandle");
class Resizable extends core_1.AbstractPureComponent {
    static defaultProps = {
        isResizable: true,
        minSize: 0,
    };
    static getDerivedStateFromProps({ size }, prevState) {
        if (prevState == null) {
            return {
                size,
                unclampedSize: size,
            };
        }
        return null;
    }
    state = Resizable.getDerivedStateFromProps(this.props, null);
    componentDidUpdate(prevProps) {
        if (prevProps.size !== this.props.size) {
            this.setState(Resizable.getDerivedStateFromProps(this.props, null));
        }
    }
    render() {
        const child = react_1.Children.only(this.props.children);
        const style = { ...child.props.style, ...this.getStyle() };
        if (this.props.isResizable === false) {
            return (0, react_1.cloneElement)(child, { style });
        }
        const resizeHandle = this.renderResizeHandle();
        return (0, react_1.cloneElement)(child, { resizeHandle, style });
    }
    renderResizeHandle() {
        const { onLayoutLock, onDoubleClick, orientation } = this.props;
        return ((0, jsx_runtime_1.jsx)(resizeHandle_1.ResizeHandle, { onDoubleClick: onDoubleClick, onLayoutLock: onLayoutLock, onResizeEnd: this.onResizeEnd, onResizeMove: this.onResizeMove, orientation: orientation }, "resize-handle"));
    }
    onResizeMove = (_offset, delta) => {
        this.offsetSize(delta);
        this.props.onSizeChanged?.(this.state.size);
    };
    onResizeEnd = (_offset) => {
        // reset "unclamped" size on end
        this.setState({ unclampedSize: this.state.size });
        this.props.onResizeEnd?.(this.state.size);
    };
    /**
     * Returns the CSS style to apply to the child element given the state's
     * size value.
     */
    getStyle() {
        if (this.props.orientation === resizeHandle_1.Orientation.VERTICAL) {
            return {
                flexBasis: `${this.state.size}px`,
                minWidth: "0px",
                width: `${this.state.size}px`,
            };
        }
        else {
            return {
                flexBasis: `${this.state.size}px`,
                height: `${this.state.size}px`,
                minHeight: "0px",
            };
        }
    }
    offsetSize(offset) {
        const unclampedSize = this.state.unclampedSize + offset;
        this.setState({
            size: index_1.Utils.clamp(unclampedSize, this.props.minSize, this.props.maxSize),
            unclampedSize,
        });
    }
}
exports.Resizable = Resizable;
//# sourceMappingURL=resizable.js.map