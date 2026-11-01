"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EditableName = void 0;
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
/**
 * Editable name component.
 *
 * @see https://blueprintjs.com/docs/#table/api.editablename
 */
exports.EditableName = (0, react_1.forwardRef)((props, ref) => {
    const { className, name, index, intent, onCancel, onChange, onConfirm } = props;
    const [dirtyName, setDirtyName] = (0, react_1.useState)(name);
    const [isEditing, setIsEditing] = (0, react_1.useState)(false);
    const [savedName, setSavedName] = (0, react_1.useState)(name);
    (0, react_1.useEffect)(() => {
        setDirtyName(name);
        setSavedName(name);
    }, [name]);
    const handleEdit = (0, react_1.useCallback)(() => {
        setIsEditing(true);
        setDirtyName(savedName);
    }, [savedName]);
    const handleCancel = (0, react_1.useCallback)((value) => {
        // don't strictly need to clear the dirtyName, but it's better hygiene
        setIsEditing(false);
        setDirtyName(undefined);
        onCancel?.(value, index);
    }, [onCancel, index]);
    const handleChange = (0, react_1.useCallback)((value) => {
        setDirtyName(value);
        onChange?.(value, index);
    }, [onChange, index]);
    const handleConfirm = (0, react_1.useCallback)((value) => {
        setIsEditing(false);
        setSavedName(value);
        setDirtyName(undefined);
        onConfirm?.(value, index);
    }, [onConfirm, index]);
    return ((0, jsx_runtime_1.jsx)(core_1.EditableText, { className: (0, classnames_1.default)(className, Classes.TABLE_EDITABLE_NAME), defaultValue: name, elementRef: ref, intent: intent, minWidth: 0, onCancel: handleCancel, onChange: handleChange, onConfirm: handleConfirm, onEdit: handleEdit, placeholder: "", selectAllOnFocus: true, value: isEditing ? dirtyName : savedName }));
});
exports.EditableName.displayName = `${core_1.DISPLAYNAME_PREFIX}.EditableName`;
//# sourceMappingURL=editableName.js.map