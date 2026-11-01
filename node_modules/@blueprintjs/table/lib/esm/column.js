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
import { DISPLAYNAME_PREFIX } from "@blueprintjs/core";
import { emptyCellRenderer } from "./cell/cell";
/**
 * Column component.
 *
 * @see https://blueprintjs.com/docs/#table/api.column
 */
export class Column extends PureComponent {
    static displayName = `${DISPLAYNAME_PREFIX}.Column`;
    static defaultProps = {
        cellRenderer: emptyCellRenderer,
    };
}
//# sourceMappingURL=column.js.map