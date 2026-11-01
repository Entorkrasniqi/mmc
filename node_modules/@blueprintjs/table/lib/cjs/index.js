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
exports.Table2 = exports.Table = exports.TableLoadingOption = exports.SelectionModes = exports.RowLoadingOption = exports.Regions = exports.RegionCardinality = exports.ColumnLoadingOption = exports.EditableName = exports.RowHeaderCell = exports.HorizontalCellDivider = exports.ColumnHeaderCell = exports.DragSelectable = exports.ResizeHandle = exports.Orientation = exports.CopyCellsMenuItem = exports.Draggable = exports.Utils = exports.RenderMode = exports.Rect = exports.Grid = exports.FocusMode = exports.Clipboard = exports.Column = exports.TruncatedFormat = exports.TruncatedPopoverMode = exports.JSONFormat = exports.EditableCell2 = exports.EditableCell = exports.Cell = void 0;
var cell_1 = require("./cell/cell");
Object.defineProperty(exports, "Cell", { enumerable: true, get: function () { return cell_1.Cell; } });
// eslint-disable-next-line @typescript-eslint/no-deprecated
var editableCell_1 = require("./cell/editableCell");
Object.defineProperty(exports, "EditableCell", { enumerable: true, get: function () { return editableCell_1.EditableCell; } });
Object.defineProperty(exports, "EditableCell2", { enumerable: true, get: function () { return editableCell_1.EditableCell2; } });
var jsonFormat_1 = require("./cell/formats/jsonFormat");
Object.defineProperty(exports, "JSONFormat", { enumerable: true, get: function () { return jsonFormat_1.JSONFormat; } });
var truncatedFormat_1 = require("./cell/formats/truncatedFormat");
Object.defineProperty(exports, "TruncatedPopoverMode", { enumerable: true, get: function () { return truncatedFormat_1.TruncatedPopoverMode; } });
Object.defineProperty(exports, "TruncatedFormat", { enumerable: true, get: function () { return truncatedFormat_1.TruncatedFormat; } });
var column_1 = require("./column");
Object.defineProperty(exports, "Column", { enumerable: true, get: function () { return column_1.Column; } });
var index_1 = require("./common/index");
Object.defineProperty(exports, "Clipboard", { enumerable: true, get: function () { return index_1.Clipboard; } });
Object.defineProperty(exports, "FocusMode", { enumerable: true, get: function () { return index_1.FocusMode; } });
Object.defineProperty(exports, "Grid", { enumerable: true, get: function () { return index_1.Grid; } });
Object.defineProperty(exports, "Rect", { enumerable: true, get: function () { return index_1.Rect; } });
Object.defineProperty(exports, "RenderMode", { enumerable: true, get: function () { return index_1.RenderMode; } });
Object.defineProperty(exports, "Utils", { enumerable: true, get: function () { return index_1.Utils; } });
var draggable_1 = require("./interactions/draggable");
Object.defineProperty(exports, "Draggable", { enumerable: true, get: function () { return draggable_1.Draggable; } });
var menus_1 = require("./interactions/menus");
Object.defineProperty(exports, "CopyCellsMenuItem", { enumerable: true, get: function () { return menus_1.CopyCellsMenuItem; } });
var resizeHandle_1 = require("./interactions/resizeHandle");
Object.defineProperty(exports, "Orientation", { enumerable: true, get: function () { return resizeHandle_1.Orientation; } });
Object.defineProperty(exports, "ResizeHandle", { enumerable: true, get: function () { return resizeHandle_1.ResizeHandle; } });
var selectable_1 = require("./interactions/selectable");
Object.defineProperty(exports, "DragSelectable", { enumerable: true, get: function () { return selectable_1.DragSelectable; } });
var columnHeaderCell_1 = require("./headers/columnHeaderCell");
Object.defineProperty(exports, "ColumnHeaderCell", { enumerable: true, get: function () { return columnHeaderCell_1.ColumnHeaderCell; } });
var horizontalCellDivider_1 = require("./headers/horizontalCellDivider");
Object.defineProperty(exports, "HorizontalCellDivider", { enumerable: true, get: function () { return horizontalCellDivider_1.HorizontalCellDivider; } });
var rowHeaderCell_1 = require("./headers/rowHeaderCell");
Object.defineProperty(exports, "RowHeaderCell", { enumerable: true, get: function () { return rowHeaderCell_1.RowHeaderCell; } });
var editableName_1 = require("./headers/editableName");
Object.defineProperty(exports, "EditableName", { enumerable: true, get: function () { return editableName_1.EditableName; } });
var regions_1 = require("./regions");
Object.defineProperty(exports, "ColumnLoadingOption", { enumerable: true, get: function () { return regions_1.ColumnLoadingOption; } });
Object.defineProperty(exports, "RegionCardinality", { enumerable: true, get: function () { return regions_1.RegionCardinality; } });
Object.defineProperty(exports, "Regions", { enumerable: true, get: function () { return regions_1.Regions; } });
Object.defineProperty(exports, "RowLoadingOption", { enumerable: true, get: function () { return regions_1.RowLoadingOption; } });
Object.defineProperty(exports, "SelectionModes", { enumerable: true, get: function () { return regions_1.SelectionModes; } });
Object.defineProperty(exports, "TableLoadingOption", { enumerable: true, get: function () { return regions_1.TableLoadingOption; } });
// eslint-disable-next-line @typescript-eslint/no-deprecated
var table_1 = require("./table");
Object.defineProperty(exports, "Table", { enumerable: true, get: function () { return table_1.Table; } });
Object.defineProperty(exports, "Table2", { enumerable: true, get: function () { return table_1.Table2; } });
//# sourceMappingURL=index.js.map