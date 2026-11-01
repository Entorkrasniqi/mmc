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
import { PureComponent } from "react";
import { MenuItem } from "@blueprintjs/core";
import { Clipboard } from "../../common/clipboard";
import { TABLE_COPY_FAILED } from "../../common/errors";
import { Regions } from "../../regions";
export class CopyCellsMenuItem extends PureComponent {
    render() {
        const { context, getCellData, onCopy, ...menuItemProps } = this.props;
        return _jsx(MenuItem, { ...menuItemProps, onClick: this.handleClick });
    }
    handleClick = () => {
        const { context, getCellData, onCopy } = this.props;
        const cells = context.getUniqueCells();
        const sparse = Regions.sparseMapCells(cells, getCellData);
        if (sparse !== undefined) {
            Clipboard.copyCells(sparse)
                .then(() => onCopy?.(true))
                .catch((reason) => {
                console.error(TABLE_COPY_FAILED, reason);
                onCopy?.(false);
            });
        }
    };
}
//# sourceMappingURL=copyCellsMenuItem.js.map