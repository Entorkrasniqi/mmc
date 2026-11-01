"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.renderFilteredItems = renderFilteredItems;
/**
 * Helper method for rendering each item in `filteredItems`, with optional support for
 * `noResults` (when filtered items is empty) and `initialContent` (when query is empty).
 *
 * This utility is useful when creating a custom `itemListRenderer`. It handles the
 * logic for rendering `initialContent`, `noResults`, or the actual list of filtered items.
 *
 * @param props Props passed to the item list renderer.
 * @param noResults Optional element to render when the filtered list is empty.
 * @param initialContent Optional element to render when the query is empty.
 * @returns The rendered list of items or the appropriate placeholder content.
 */
function renderFilteredItems(props, noResults, initialContent) {
    if (props.query.length === 0 && initialContent !== undefined) {
        return initialContent;
    }
    const items = props.filteredItems.map(props.renderItem).filter(item => item != null);
    return items.length > 0 ? items : noResults;
}
//# sourceMappingURL=itemListRenderer.js.map