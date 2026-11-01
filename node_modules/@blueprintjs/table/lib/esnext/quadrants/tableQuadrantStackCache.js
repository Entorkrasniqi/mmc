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
export class TableQuadrantStackCache {
    cachedRowHeaderWidth = 0;
    cachedColumnHeaderHeight = 0;
    cachedScrollLeft = 0;
    cachedScrollTop = 0;
    cachedScrollContainerClientWidth;
    cachedScrollContainerClientHeight;
    constructor() {
        this.reset();
    }
    reset() {
        this.cachedRowHeaderWidth = 0;
        this.cachedColumnHeaderHeight = 0;
        this.cachedScrollLeft = 0;
        this.cachedScrollTop = 0;
    }
    // Getters
    // =======
    getScrollOffset(scrollKey) {
        return scrollKey === "scrollLeft" ? this.cachedScrollLeft : this.cachedScrollTop;
    }
    getRowHeaderWidth() {
        return this.cachedRowHeaderWidth;
    }
    getColumnHeaderHeight() {
        return this.cachedColumnHeaderHeight;
    }
    getScrollContainerClientWidth() {
        return this.cachedScrollContainerClientWidth;
    }
    getScrollContainerClientHeight() {
        return this.cachedScrollContainerClientHeight;
    }
    // Setters
    // =======
    setColumnHeaderHeight(height) {
        this.cachedColumnHeaderHeight = height;
    }
    setRowHeaderWidth(width) {
        this.cachedRowHeaderWidth = width;
    }
    setScrollOffset(scrollKey, offset) {
        if (scrollKey === "scrollLeft") {
            this.cachedScrollLeft = offset;
        }
        else {
            this.cachedScrollTop = offset;
        }
    }
    setScrollContainerClientWidth(clientWidth) {
        this.cachedScrollContainerClientWidth = clientWidth;
    }
    setScrollContainerClientHeight(clientHeight) {
        this.cachedScrollContainerClientHeight = clientHeight;
    }
}
//# sourceMappingURL=tableQuadrantStackCache.js.map