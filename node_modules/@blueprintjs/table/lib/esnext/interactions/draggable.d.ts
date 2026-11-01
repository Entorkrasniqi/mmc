import { PureComponent } from "react";
import { type Props } from "@blueprintjs/core";
import type { DraggableChildrenProps, DragHandler } from "./dragTypes";
export type DraggableProps = Props & DragHandler & DraggableChildrenProps;
/**
 * This component provides a simple interface for combined drag and/or click events.
 *
 * Like ResizeSensor, this component expects a single child element so that it can
 * clone it and attach a ref to it.
 *
 * Since the mouse interactions for drag and click are overloaded, here are
 * the events that will fire in these cases:
 *
 * A Click Interaction
 * 1. The user presses down on the render element, triggering the onActivate
 *    callback.
 * 2. The user releases the mouse button without moving it, triggering the
 *    onClick callback.
 *
 * A Drag Interaction
 * 1. The user presses down on the render element, triggering the onActivate
 *    callback.
 * 2. The user moves the mouse, triggering the onDragMove callback.
 * 3. The user moves the mouse, triggering the onDragMove callback.
 * 4. The user moves the mouse, triggering the onDragMove callback.
 * 5. The user releases the mouse button, triggering a final onDragMove
 *    callback as well as an onDragEnd callback.
 *
 * If `false` is returned from the onActivate callback, no further events
 * will be fired until the next activation.
 */
export declare class Draggable extends PureComponent<DraggableProps> {
    static defaultProps: {
        preventDefault: boolean;
        stopPropagation: boolean;
    };
    private events;
    private targetRef;
    render(): import("react").JSX.Element;
    componentDidUpdate(prevProps: DraggableProps): void;
    componentDidMount(): void;
    componentWillUnmount(): void;
}
