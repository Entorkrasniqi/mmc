"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SeeTag = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const common_1 = require("../common");
const context_1 = require("../common/context");
const SeeTag = ({ value }) => {
    const { renderType } = (0, react_1.useContext)(context_1.DocumentationContext);
    return (0, jsx_runtime_1.jsxs)("p", { children: ["See: ", renderType(value)] });
};
exports.SeeTag = SeeTag;
exports.SeeTag.displayName = `${common_1.COMPONENT_DISPLAY_NAMESPACE}.SeeTag`;
//# sourceMappingURL=see.js.map