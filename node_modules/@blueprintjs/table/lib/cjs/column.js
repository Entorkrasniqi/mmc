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
exports.Column = void 0;
const react_1 = require("react");
const core_1 = require("@blueprintjs/core");
const cell_1 = require("./cell/cell");
/**
 * Column component.
 *
 * @see https://blueprintjs.com/docs/#table/api.column
 */
class Column extends react_1.PureComponent {
    static displayName = `${core_1.DISPLAYNAME_PREFIX}.Column`;
    static defaultProps = {
        cellRenderer: cell_1.emptyCellRenderer,
    };
}
exports.Column = Column;
//# sourceMappingURL=column.js.map