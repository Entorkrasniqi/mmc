/* !
 * (c) Copyright 2024 Palantir Technologies Inc. All rights reserved.
 */
export class ReactCodeExampleTagRenderer {
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
//# sourceMappingURL=reactCodeExample.js.map