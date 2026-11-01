"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Cell = exports.emptyCellRenderer = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2016 Palantir Technologies, Inc. All rights reserved.
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
const loadableContent_1 = require("../common/loadableContent");
const jsonFormat_1 = require("./formats/jsonFormat");
const truncatedFormat_1 = require("./formats/truncatedFormat");
const emptyCellRenderer = () => (0, jsx_runtime_1.jsx)(Cell, {});
exports.emptyCellRenderer = emptyCellRenderer;
/**
 * Cell component.
 *
 * @see https://blueprintjs.com/docs/#table/api.cell
 */
class Cell extends react_1.Component {
    static displayName = `${core_1.DISPLAYNAME_PREFIX}.Cell`;
    static defaultProps = {
        truncated: true,
        wrapText: false,
    };
    shouldComponentUpdate(nextProps) {
        // deeply compare "style," because a new but identical object might have been provided.
        return (!core_1.Utils.shallowCompareKeys(this.props, nextProps, { exclude: ["style"] }) ||
            !core_1.Utils.deepCompareKeys(this.props.style, nextProps.style));
    }
    render() {
        const { cellRef, tabIndex, onKeyDown, onKeyUp, onKeyPress, style, intent, interactive, loading, tooltip, truncated, className, wrapText, } = this.props;
        const classes = (0, classnames_1.default)(Classes.TABLE_CELL, core_1.Classes.intentClass(intent), {
            [Classes.TABLE_CELL_INTERACTIVE]: interactive,
            [core_1.Classes.LOADING]: loading,
            [Classes.TABLE_TRUNCATED_CELL]: truncated,
        }, className);
        const textClasses = (0, classnames_1.default)({
            [Classes.TABLE_TRUNCATED_TEXT]: truncated,
            [Classes.TABLE_NO_WRAP_TEXT]: !wrapText,
        });
        // add width and height to the children, for use in shouldComponentUpdate in truncatedFormat
        // note: these aren't actually used by truncated format, just in shouldComponentUpdate
        const modifiedChildren = react_1.Children.map(this.props.children, child => {
            const isFormatElement = core_1.Utils.isElementOfType(child, truncatedFormat_1.TruncatedFormat) || core_1.Utils.isElementOfType(child, jsonFormat_1.JSONFormat);
            if (style != null && (0, react_1.isValidElement)(child) && isFormatElement) {
                return (0, react_1.cloneElement)(child, {
                    parentCellHeight: style.height === undefined ? undefined : parseInt(style.height.toString(), 10),
                    parentCellWidth: style.width === undefined ? undefined : parseInt(style.width.toString(), 10),
                });
            }
            return child;
        });
        const content = (0, jsx_runtime_1.jsx)("div", { className: textClasses, children: modifiedChildren });
        return ((0, jsx_runtime_1.jsx)("div", { className: classes, title: tooltip, ref: cellRef, onKeyDown, onKeyPress, onKeyUp, style, tabIndex, children: (0, jsx_runtime_1.jsx)(loadableContent_1.LoadableContent, { loading: loading ?? false, variableLength: true, children: content }) }));
    }
}
exports.Cell = Cell;
//# sourceMappingURL=cell.js.map