"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.MenuContextImpl = void 0;
const regions_1 = require("../../regions");
class MenuContextImpl {
    target;
    selectedRegions;
    numRows;
    numCols;
    regions;
    constructor(target, selectedRegions, numRows, numCols) {
        this.target = target;
        this.selectedRegions = selectedRegions;
        this.numRows = numRows;
        this.numCols = numCols;
        this.regions = regions_1.Regions.overlapsRegion(selectedRegions, target) ? selectedRegions : [target];
    }
    getTarget() {
        return this.target;
    }
    getSelectedRegions() {
        return this.selectedRegions;
    }
    getRegions() {
        return this.regions;
    }
    getUniqueCells() {
        return regions_1.Regions.enumerateUniqueCells(this.regions, this.numRows, this.numCols);
    }
}
exports.MenuContextImpl = MenuContextImpl;
//# sourceMappingURL=menuContext.js.map