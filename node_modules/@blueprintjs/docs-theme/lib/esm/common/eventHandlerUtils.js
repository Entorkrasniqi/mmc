/*
 * Copyright 2017 Palantir Technologies, Inc. All rights reserved.
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
export function createKeyEventHandler(actions, preventDefault = false) {
    return (e) => {
        for (const key of Object.keys(actions)) {
            const isSpacebarEvent = e.key === " ";
            if (e.key === key || (isSpacebarEvent && key === "Space")) {
                if (preventDefault) {
                    e.preventDefault();
                }
                actions[key]?.(e);
            }
        }
        actions.all?.(e);
    };
}
/** Event handler that exposes the target element's value as a boolean. */
export function handleBooleanChange(handler) {
    return (event) => handler(event.target.checked);
}
/** Event handler that exposes the target element's value as a string. */
export function handleStringChange(handler) {
    return (event) => handler(event.target.value);
}
/** Event handler that exposes the target element's value as an inferred generic type. */
export function handleValueChange(handler) {
    return (event) => handler(event.target.value);
}
/** Event handler that exposes the target element's value as a number. */
export function handleNumberChange(handler) {
    return handleStringChange(value => handler(+value));
}
//# sourceMappingURL=eventHandlerUtils.js.map