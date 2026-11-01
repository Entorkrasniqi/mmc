"use strict";
/* !
 * (c) Copyright 2025 Palantir Technologies Inc. All rights reserved.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ThemeProvider = exports.useTheme = exports.ThemeContext = void 0;
const react_1 = require("react");
exports.ThemeContext = (0, react_1.createContext)({
    isDarkTheme: false,
});
const useTheme = () => (0, react_1.useContext)(exports.ThemeContext);
exports.useTheme = useTheme;
exports.ThemeProvider = exports.ThemeContext.Provider;
//# sourceMappingURL=themeContext.js.map