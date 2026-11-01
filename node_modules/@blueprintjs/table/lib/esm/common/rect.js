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
/**
 * A simple object for storing the client bounds of HTMLElements. Since
 * ClientRects are immutable, this object enables editing and some simple
 * manipulation methods.
 */
export class Rect {
    left;
    top;
    width;
    height;
    static ORIGIN = new Rect(0, 0, 0, 0);
    /**
     * Returns the smallest Rect that entirely contains the supplied rects
     */
    static union(anyRect0, anyRect1) {
        const rect0 = Rect.wrap(anyRect0);
        const rect1 = Rect.wrap(anyRect1);
        const top = Math.min(rect0.top, rect1.top);
        const left = Math.min(rect0.left, rect1.left);
        const bottom = Math.max(rect0.top + rect0.height, rect1.top + rect1.height);
        const right = Math.max(rect0.left + rect0.width, rect1.left + rect1.width);
        const height = bottom - top;
        const width = right - left;
        return new Rect(left, top, width, height);
    }
    /**
     * Returns a new Rect that subtracts the origin of the second argument
     * from the first.
     */
    static subtractOrigin(anyRect0, anyRect1) {
        const rect0 = Rect.wrap(anyRect0);
        const rect1 = Rect.wrap(anyRect1);
        return new Rect(rect0.left - rect1.left, rect0.top - rect1.top, rect0.width, rect0.height);
    }
    /**
     * Returns the CSS properties representing the absolute positioning of
     * this Rect.
     */
    static style(rect) {
        return {
            height: `${rect.height}px`,
            left: `${rect.left}px`,
            position: "absolute",
            top: `${rect.top}px`,
            width: `${rect.width}px`,
        };
    }
    /**
     * Given a DOMRect or Rect object, returns a Rect object.
     */
    static wrap(rect) {
        if (rect instanceof Rect) {
            return rect;
        }
        else {
            return new Rect(rect.left, rect.top, rect.width, rect.height);
        }
    }
    constructor(left, top, width, height) {
        this.left = left;
        this.top = top;
        this.width = width;
        this.height = height;
    }
    subtractOrigin(anyRect) {
        return Rect.subtractOrigin(this, anyRect);
    }
    union(anyRect) {
        return Rect.union(this, anyRect);
    }
    style() {
        return Rect.style(this);
    }
    sizeStyle() {
        return {
            height: `${this.height}px`,
            width: `${this.width}px`,
        };
    }
    containsX(clientX) {
        return clientX >= this.left && clientX <= this.left + this.width;
    }
    containsY(clientY) {
        return clientY >= this.top && clientY <= this.top + this.height;
    }
    equals(rect) {
        return (rect != null &&
            this.left === rect.left &&
            this.top === rect.top &&
            this.width === rect.width &&
            this.height === rect.height);
    }
}
//# sourceMappingURL=rect.js.map