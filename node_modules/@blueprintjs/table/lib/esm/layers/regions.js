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
import classNames from "classnames";
import { Component } from "react";
import { Utils as CoreUtils } from "@blueprintjs/core";
import * as Classes from "../common/classes";
import { Regions } from "../regions";
// don't include "regions" or "regionStyles" in here, because they can't be shallowly compared
const UPDATE_PROPS_KEYS = ["className"];
export class RegionLayer extends Component {
    shouldComponentUpdate(nextProps) {
        // shallowly comparable props like "className" tend not to change in the default table
        // implementation, so do that check last with hope that we return earlier and avoid it
        // altogether.
        return (!CoreUtils.arraysEqual(this.props.regions ?? [], nextProps.regions ?? [], Regions.regionsEqual) ||
            !CoreUtils.arraysEqual(this.props.regionStyles ?? [], nextProps.regionStyles ?? [], CoreUtils.shallowCompareKeys) ||
            !CoreUtils.shallowCompareKeys(this.props, nextProps, { include: UPDATE_PROPS_KEYS }));
    }
    render() {
        return _jsx("div", { className: Classes.TABLE_OVERLAY_LAYER, children: this.renderRegionChildren() });
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
        return (_jsx("div", { className: classNames(Classes.TABLE_OVERLAY, Classes.TABLE_REGION, className), style: regionStyles === undefined ? undefined : regionStyles[index] }, index));
    };
}
//# sourceMappingURL=regions.js.map