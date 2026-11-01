"use strict";
/*
 * Copyright 2019 Palantir Technologies, Inc. All rights reserved.
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
exports.FixList = void 0;
class FixList {
    constructor() {
        this.fixes = [];
    }
    getFixes() {
        return this.fixes;
    }
    addFixes(fixes) {
        if (fixes == null) {
            return;
        }
        else if (isRuleFix(fixes)) {
            this.fixes.push(fixes);
        }
        else {
            this.fixes = this.fixes.concat(Array.from(fixes));
        }
    }
}
exports.FixList = FixList;
function isRuleFix(fix) {
    return fix.range !== undefined && fix.text !== undefined;
}
//# sourceMappingURL=fixList.js.map