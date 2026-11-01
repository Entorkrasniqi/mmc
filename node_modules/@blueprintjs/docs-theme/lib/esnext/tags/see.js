import { jsxs as _jsxs } from "react/jsx-runtime";
import { useContext } from "react";
import { COMPONENT_DISPLAY_NAMESPACE } from "../common";
import { DocumentationContext } from "../common/context";
export const SeeTag = ({ value }) => {
    const { renderType } = useContext(DocumentationContext);
    return _jsxs("p", { children: ["See: ", renderType(value)] });
};
SeeTag.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.SeeTag`;
//# sourceMappingURL=see.js.map