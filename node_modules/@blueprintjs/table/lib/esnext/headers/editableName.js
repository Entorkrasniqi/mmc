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
import { forwardRef, useCallback, useEffect, useState } from "react";
import { DISPLAYNAME_PREFIX, EditableText } from "@blueprintjs/core";
import * as Classes from "../common/classes";
/**
 * Editable name component.
 *
 * @see https://blueprintjs.com/docs/#table/api.editablename
 */
export const EditableName = forwardRef((props, ref) => {
    const { className, name, index, intent, onCancel, onChange, onConfirm } = props;
    const [dirtyName, setDirtyName] = useState(name);
    const [isEditing, setIsEditing] = useState(false);
    const [savedName, setSavedName] = useState(name);
    useEffect(() => {
        setDirtyName(name);
        setSavedName(name);
    }, [name]);
    const handleEdit = useCallback(() => {
        setIsEditing(true);
        setDirtyName(savedName);
    }, [savedName]);
    const handleCancel = useCallback((value) => {
        // don't strictly need to clear the dirtyName, but it's better hygiene
        setIsEditing(false);
        setDirtyName(undefined);
        onCancel?.(value, index);
    }, [onCancel, index]);
    const handleChange = useCallback((value) => {
        setDirtyName(value);
        onChange?.(value, index);
    }, [onChange, index]);
    const handleConfirm = useCallback((value) => {
        setIsEditing(false);
        setSavedName(value);
        setDirtyName(undefined);
        onConfirm?.(value, index);
    }, [onConfirm, index]);
    return (_jsx(EditableText, { className: classNames(className, Classes.TABLE_EDITABLE_NAME), defaultValue: name, elementRef: ref, intent: intent, minWidth: 0, onCancel: handleCancel, onChange: handleChange, onConfirm: handleConfirm, onEdit: handleEdit, placeholder: "", selectAllOnFocus: true, value: isEditing ? dirtyName : savedName }));
});
EditableName.displayName = `${DISPLAYNAME_PREFIX}.EditableName`;
//# sourceMappingURL=editableName.js.map