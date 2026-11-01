"use strict";
/* !
 * (c) Copyright 2024 Palantir Technologies Inc. All rights reserved.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ReactCodeExampleTagRenderer = void 0;
class ReactCodeExampleTagRenderer {
    examples;
    constructor(examples) {
        this.examples = examples;
    }
    render = ({ value: exampleName }) => {
        if (exampleName == null) {
            return null;
        }
        const example = this.examples[exampleName];
        if (example == null) {
            throw new Error(`Unknown @example component: ${exampleName}`);
        }
        return example.render({ id: exampleName }) ?? null;
    };
}
exports.ReactCodeExampleTagRenderer = ReactCodeExampleTagRenderer;
//# sourceMappingURL=reactCodeExample.js.map