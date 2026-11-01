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
import { Children, cloneElement } from "react";
import { AbstractPureComponent } from "@blueprintjs/core";
import { Utils } from "../common/index";
import { Orientation, ResizeHandle } from "./resizeHandle";
export class Resizable extends AbstractPureComponent {
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
        const child = Children.only(this.props.children);
        const style = { ...child.props.style, ...this.getStyle() };
        if (this.props.isResizable === false) {
            return cloneElement(child, { style });
        }
        const resizeHandle = this.renderResizeHandle();
        return cloneElement(child, { resizeHandle, style });
    }
    renderResizeHandle() {
        const { onLayoutLock, onDoubleClick, orientation } = this.props;
        return (_jsx(ResizeHandle, { onDoubleClick: onDoubleClick, onLayoutLock: onLayoutLock, onResizeEnd: this.onResizeEnd, onResizeMove: this.onResizeMove, orientation: orientation }, "resize-handle"));
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
        if (this.props.orientation === Orientation.VERTICAL) {
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
            size: Utils.clamp(unclampedSize, this.props.minSize, this.props.maxSize),
            unclampedSize,
        });
    }
}
//# sourceMappingURL=resizable.js.map