"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.FilmSelect = FilmSelect;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2021 Palantir Technologies, Inc. All rights reserved.
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
const core_1 = require("@blueprintjs/core");
const select_1 = require("../components/select/select");
const films_1 = require("./films");
function FilmSelect({ allowCreate = false, fill, ...restProps }) {
    const [items, setItems] = (0, react_1.useState)([...films_1.TOP_100_FILMS]);
    const [createdItems, setCreatedItems] = (0, react_1.useState)([]);
    const [selectedFilm, setSelectedFilm] = (0, react_1.useState)(undefined);
    const handleItemSelect = (0, react_1.useCallback)((newFilm) => {
        // Delete the old film from the list if it was newly created.
        const step1Result = (0, films_1.maybeDeleteCreatedFilmFromArrays)(items, createdItems, selectedFilm);
        // Add the new film to the list if it is newly created.
        const step2Result = (0, films_1.maybeAddCreatedFilmToArrays)(step1Result.items, step1Result.createdItems, newFilm);
        setCreatedItems(step2Result.createdItems);
        setSelectedFilm(newFilm);
        setItems(step2Result.items);
    }, [createdItems, items, selectedFilm]);
    const itemRenderer = (0, react_1.useCallback)((film, props) => {
        if (!props.modifiers.matchesPredicate) {
            return null;
        }
        return ((0, jsx_runtime_1.jsx)(core_1.MenuItem, { ...(0, films_1.getFilmItemProps)(film, props), roleStructure: "listoption", selected: film === selectedFilm, tagName: "div" }, film.rank));
    }, [selectedFilm]);
    return ((0, jsx_runtime_1.jsx)(select_1.Select, { createNewItemFromQuery: allowCreate ? films_1.createFilm : undefined, createNewItemRenderer: allowCreate ? films_1.renderCreateFilmMenuItem : undefined, fill: fill, itemPredicate: films_1.filterFilm, itemRenderer: itemRenderer, items: items, itemsEqual: films_1.areFilmsEqual, menuProps: { "aria-label": "films" }, noResults: (0, jsx_runtime_1.jsx)(core_1.MenuItem, { disabled: true, text: "No results.", roleStructure: "listoption" }), onItemSelect: handleItemSelect, ...restProps, children: (0, jsx_runtime_1.jsx)(core_1.Button, { alignText: "start", disabled: restProps.disabled, endIcon: "caret-down", fill: fill, icon: "film", text: maybeRenderSelectedFilm(selectedFilm) ?? "(No selection)", textClassName: (0, classnames_1.default)({
                [core_1.Classes.TEXT_MUTED]: selectedFilm === undefined,
            }) }) }));
}
function maybeRenderSelectedFilm(selectedFilm) {
    return selectedFilm ? `${selectedFilm.title} (${selectedFilm.year})` : undefined;
}
//# sourceMappingURL=filmSelect.js.map