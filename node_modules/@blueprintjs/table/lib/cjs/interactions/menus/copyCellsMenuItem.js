"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CopyCellsMenuItem = void 0;
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
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const clipboard_1 = require("../../common/clipboard");
const errors_1 = require("../../common/errors");
const regions_1 = require("../../regions");
class CopyCellsMenuItem extends react_1.PureComponent {
    render() {
        const { context, getCellData, onCopy, ...menuItemProps } = this.props;
        return (0, jsx_runtime_1.jsx)(core_1.MenuItem, { ...menuItemProps, onClick: this.handleClick });
    }
    handleClick = () => {
        const { context, getCellData, onCopy } = this.props;
        const cells = context.getUniqueCells();
        const sparse = regions_1.Regions.sparseMapCells(cells, getCellData);
        if (sparse !== undefined) {
            clipboard_1.Clipboard.copyCells(sparse)
                .then(() => onCopy?.(true))
                .catch((reason) => {
                console.error(errors_1.TABLE_COPY_FAILED, reason);
                onCopy?.(false);
            });
        }
    };
}
exports.CopyCellsMenuItem = CopyCellsMenuItem;
//# sourceMappingURL=copyCellsMenuItem.js.map