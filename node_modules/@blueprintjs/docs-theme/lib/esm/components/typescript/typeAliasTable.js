import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import classNames from "classnames";
import { useContext } from "react";
import { COMPONENT_DISPLAY_NAMESPACE } from "../../common";
import { DocumentationContext } from "../../common/context";
import { ApiHeader } from "./apiHeader";
export const TypeAliasTable = ({ className, data }) => {
    const { renderBlock, renderType } = useContext(DocumentationContext);
    const aliases = data.type.split(" | ").map((type, i) => (_jsxs("div", { children: [i === 0 ? "=" : "|", " ", renderType(type)] }, i)));
    return (_jsxs("div", { className: classNames("docs-modifiers", className), children: [_jsx(ApiHeader, { ...data }), renderBlock(data.documentation), _jsx("div", { className: "docs-type-alias docs-code", children: aliases })] }));
};
TypeAliasTable.displayName = `${COMPONENT_DISPLAY_NAMESPACE}.TypeAliasTable`;
//# sourceMappingURL=typeAliasTable.js.map