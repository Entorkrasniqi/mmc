/* !
 * (c) Copyright 2025 Palantir Technologies Inc. All rights reserved.
 */
import { createContext, useContext } from "react";
export const ThemeContext = createContext({
    isDarkTheme: false,
});
export const useTheme = () => useContext(ThemeContext);
export const ThemeProvider = ThemeContext.Provider;
//# sourceMappingURL=themeContext.js.map