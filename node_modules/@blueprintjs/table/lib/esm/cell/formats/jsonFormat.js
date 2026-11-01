import { jsx as _jsx } from "react/jsx-runtime";
/*
 * Copyright 2022 Palantir Technologies, Inc. All rights reserved.
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
import { DISPLAYNAME_PREFIX } from "@blueprintjs/core";
import * as Classes from "../../common/classes";
import { TruncatedFormat, TruncatedPopoverMode } from "./truncatedFormat";
/* istanbul ignore next */
/**
 * JSON cell format component.
 *
 * @see https://blueprintjs.com/docs/#table/api.jsonformat
 */
export class JSONFormat extends Component {
    static displayName = `${DISPLAYNAME_PREFIX}.JSONFormat`;
    static defaultProps = {
        omitQuotesOnStrings: true,
        stringify: (obj) => JSON.stringify(obj, null, 2),
    };
    render() {
        const { children, omitQuotesOnStrings, stringify } = this.props;
        let { showPopover } = this.props;
        // always hide popover if value is nully
        const isNully = children == null;
        if (isNully) {
            showPopover = TruncatedPopoverMode.NEVER;
        }
        const className = classNames(this.props.className, {
            [Classes.TABLE_NULL]: isNully,
        });
        let displayValue = "";
        if (omitQuotesOnStrings && typeof children === "string") {
            displayValue = children;
        }
        else {
            displayValue = stringify(children);
        }
        return (_jsx(TruncatedFormat, { ...this.props, className: className, showPopover: showPopover, children: displayValue }));
    }
}
//# sourceMappingURL=jsonFormat.js.map