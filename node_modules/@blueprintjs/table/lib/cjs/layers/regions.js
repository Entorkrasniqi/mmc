"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RegionLayer = void 0;
const tslib_1 = require("tslib");
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
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const Classes = tslib_1.__importStar(require("../common/classes"));
const regions_1 = require("../regions");
// don't include "regions" or "regionStyles" in here, because they can't be shallowly compared
const UPDATE_PROPS_KEYS = ["className"];
class RegionLayer extends react_1.Component {
    shouldComponentUpdate(nextProps) {
        // shallowly comparable props like "className" tend not to change in the default table
        // implementation, so do that check last with hope that we return earlier and avoid it
        // altogether.
        return (!core_1.Utils.arraysEqual(this.props.regions ?? [], nextProps.regions ?? [], regions_1.Regions.regionsEqual) ||
            !core_1.Utils.arraysEqual(this.props.regionStyles ?? [], nextProps.regionStyles ?? [], core_1.Utils.shallowCompareKeys) ||
            !core_1.Utils.shallowCompareKeys(this.props, nextProps, { include: UPDATE_PROPS_KEYS }));
    }
    render() {
        return (0, jsx_runtime_1.jsx)("div", { className: Classes.TABLE_OVERLAY_LAYER, children: this.renderRegionChildren() });
    }
    renderRegionChildren() {
        const { regions } = this.props;
        if (regions == null) {
            return undefined;
        }
        return regions.map(this.renderRegion);
    }
    renderRegion = (_region, index) => {
        const { className, regionStyles } = this.props;
        return ((0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)(Classes.TABLE_OVERLAY, Classes.TABLE_REGION, className), style: regionStyles === undefined ? undefined : regionStyles[index] }, index));
    };
}
exports.RegionLayer = RegionLayer;
//# sourceMappingURL=regions.js.map