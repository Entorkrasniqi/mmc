"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EditableCell2 = exports.EditableCell = void 0;
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
const draggable_1 = require("../interactions/draggable");
const cell_1 = require("./cell");
/**
 * Editable cell component.
 *
 * @see https://blueprintjs.com/docs/#table/api.editablecell
 */
class EditableCell extends react_1.Component {
    static displayName = `${core_1.DISPLAYNAME_PREFIX}.EditableCell`;
    static defaultProps = {
        truncated: true,
        wrapText: false,
    };
    cellRef = (0, react_1.createRef)();
    contentsRef = (0, react_1.createRef)();
    state = {
        isEditing: false,
        savedValue: this.props.value,
    };
    componentDidMount() {
        this.checkShouldFocus();
    }
    componentDidUpdate(prevProps) {
        const didPropsChange = !core_1.Utils.shallowCompareKeys(this.props, prevProps, { exclude: ["style"] }) ||
            !core_1.Utils.deepCompareKeys(this.props, prevProps, ["style"]);
        const { value } = this.props;
        if (didPropsChange && value != null) {
            this.setState({ dirtyValue: value, savedValue: value });
        }
        this.checkShouldFocus();
    }
    shouldComponentUpdate(nextProps, nextState) {
        return (!core_1.Utils.shallowCompareKeys(this.props, nextProps, { exclude: ["style"] }) ||
            !core_1.Utils.shallowCompareKeys(this.state, nextState) ||
            !core_1.Utils.deepCompareKeys(this.props, nextProps, ["style"]));
    }
    render() {
        return (0, jsx_runtime_1.jsx)(core_1.HotkeysTarget, { hotkeys: this.hotkeys, children: this.renderCell });
    }
    renderCell = ({ handleKeyDown, handleKeyUp }) => {
        const { editableTextProps, onCancel, onChange, onConfirm, tabIndex = 0, truncated, wrapText, ...spreadableProps } = this.props;
        const { isEditing, dirtyValue, savedValue } = this.state;
        const interactive = spreadableProps.interactive || isEditing;
        let cellContents;
        if (isEditing) {
            const className = editableTextProps ? editableTextProps.className : null;
            cellContents = ((0, jsx_runtime_1.jsx)(core_1.EditableText, { ...editableTextProps, isEditing: true, className: (0, classnames_1.default)(Classes.TABLE_EDITABLE_TEXT, Classes.TABLE_EDITABLE_NAME, className), elementRef: this.contentsRef, intent: spreadableProps.intent, minWidth: 0, onCancel: this.handleCancel, onChange: this.handleChange, onConfirm: this.handleConfirm, onEdit: this.handleEdit, placeholder: "", selectAllOnFocus: false, value: dirtyValue }));
        }
        else {
            const textClasses = (0, classnames_1.default)(Classes.TABLE_EDITABLE_TEXT, {
                [Classes.TABLE_TRUNCATED_TEXT]: truncated,
                [Classes.TABLE_NO_WRAP_TEXT]: !wrapText,
            });
            cellContents = ((0, jsx_runtime_1.jsx)("div", { className: textClasses, ref: this.contentsRef, children: savedValue }));
        }
        return ((0, jsx_runtime_1.jsx)(cell_1.Cell, { ...spreadableProps, wrapText: wrapText, truncated: false, interactive: interactive, cellRef: this.cellRef, onKeyDown: handleKeyDown, onKeyPress: this.handleKeyPress, onKeyUp: handleKeyUp, tabIndex: tabIndex, children: (0, jsx_runtime_1.jsx)(draggable_1.Draggable, { onActivate: this.handleCellActivate, onDoubleClick: this.handleCellDoubleClick, preventDefault: false, stopPropagation: interactive, targetRef: this.contentsRef, children: cellContents }) }));
    };
    checkShouldFocus() {
        if (this.props.isFocused && !this.state.isEditing) {
            // don't focus if we're editing -- we'll lose the fact that we're editing
            this.cellRef.current?.focus();
        }
    }
    handleKeyPress = () => {
        if (this.state.isEditing || !this.props.isFocused) {
            return;
        }
        // setting dirty value to empty string because apparently the text field will pick up the key and write it in there
        this.setState({ dirtyValue: "", isEditing: true, savedValue: this.state.savedValue });
    };
    handleEdit = () => {
        this.setState({ dirtyValue: this.state.savedValue, isEditing: true });
    };
    handleCancel = (value) => {
        // don't strictly need to clear the dirtyValue, but it's better hygiene
        this.setState({ dirtyValue: undefined, isEditing: false });
        this.invokeCallback(this.props.onCancel, value);
    };
    handleChange = (value) => {
        this.setState({ dirtyValue: value });
        this.invokeCallback(this.props.onChange, value);
    };
    handleConfirm = (value) => {
        this.setState({ dirtyValue: undefined, isEditing: false, savedValue: value });
        this.invokeCallback(this.props.onConfirm, value);
    };
    invokeCallback(callback, value) {
        // pass through the row and column indices if they were provided as props by the consumer
        const { rowIndex, columnIndex } = this.props;
        callback?.(value, rowIndex, columnIndex);
    }
    handleCellActivate = (_event) => {
        return true;
    };
    handleCellDoubleClick = (_event) => {
        this.handleEdit();
    };
    hotkeys = [
        {
            combo: "f2",
            group: "Table",
            label: "Edit the currently focused cell",
            onKeyDown: this.handleEdit,
        },
    ];
}
exports.EditableCell = EditableCell;
/** @deprecated Use `EditableCell` instead */
exports.EditableCell2 = EditableCell;
//# sourceMappingURL=editableCell.js.map