import { jsx as _jsx } from "react/jsx-runtime";
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
import classNames from "classnames";
import { useCallback, useState } from "react";
import { Button, Classes, MenuItem } from "@blueprintjs/core";
import { Select } from "../components/select/select";
import { areFilmsEqual, createFilm, filterFilm, getFilmItemProps, maybeAddCreatedFilmToArrays, maybeDeleteCreatedFilmFromArrays, renderCreateFilmMenuItem, TOP_100_FILMS, } from "./films";
export function FilmSelect({ allowCreate = false, fill, ...restProps }) {
    const [items, setItems] = useState([...TOP_100_FILMS]);
    const [createdItems, setCreatedItems] = useState([]);
    const [selectedFilm, setSelectedFilm] = useState(undefined);
    const handleItemSelect = useCallback((newFilm) => {
        // Delete the old film from the list if it was newly created.
        const step1Result = maybeDeleteCreatedFilmFromArrays(items, createdItems, selectedFilm);
        // Add the new film to the list if it is newly created.
        const step2Result = maybeAddCreatedFilmToArrays(step1Result.items, step1Result.createdItems, newFilm);
        setCreatedItems(step2Result.createdItems);
        setSelectedFilm(newFilm);
        setItems(step2Result.items);
    }, [createdItems, items, selectedFilm]);
    const itemRenderer = useCallback((film, props) => {
        if (!props.modifiers.matchesPredicate) {
            return null;
        }
        return (_jsx(MenuItem, { ...getFilmItemProps(film, props), roleStructure: "listoption", selected: film === selectedFilm, tagName: "div" }, film.rank));
    }, [selectedFilm]);
    return (_jsx(Select, { createNewItemFromQuery: allowCreate ? createFilm : undefined, createNewItemRenderer: allowCreate ? renderCreateFilmMenuItem : undefined, fill: fill, itemPredicate: filterFilm, itemRenderer: itemRenderer, items: items, itemsEqual: areFilmsEqual, menuProps: { "aria-label": "films" }, noResults: _jsx(MenuItem, { disabled: true, text: "No results.", roleStructure: "listoption" }), onItemSelect: handleItemSelect, ...restProps, children: _jsx(Button, { alignText: "start", disabled: restProps.disabled, endIcon: "caret-down", fill: fill, icon: "film", text: maybeRenderSelectedFilm(selectedFilm) ?? "(No selection)", textClassName: classNames({
                [Classes.TEXT_MUTED]: selectedFilm === undefined,
            }) }) }));
}
function maybeRenderSelectedFilm(selectedFilm) {
    return selectedFilm ? `${selectedFilm.title} (${selectedFilm.year})` : undefined;
}
//# sourceMappingURL=filmSelect.js.map