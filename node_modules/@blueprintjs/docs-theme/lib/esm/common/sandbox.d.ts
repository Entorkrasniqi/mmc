export interface Files {
    [key: string]: {
        content: string;
        isBinary: boolean;
    };
}
export declare function getParameters(parameters: {
    files: Files;
}): string;
/**
 * Extracts import statements from TypeScript/JavaScript code
 */
export declare function extractImports(code: string): string[];
/**
 * Converts import specifiers to npm package dependencies
 */
export declare function extractDependencies(imports: string[]): Record<string, string>;
/**
 * Extracts CSS imports needed for the given import specifiers
 */
export declare function extractStylesheets(imports: string[]): string[];
/**
 * Analyzes code and extracts all necessary information for sandbox generation
 */
export declare function analyzeCode(code: string): {
    imports: string[];
    dependencies: Record<string, string>;
    stylesheets: string[];
};
export declare const getHtml: ({ title }: {
    title: string;
}) => string;
export declare const getIndex: (stylesheets?: string[], isDark?: boolean) => string;
export declare const getStyles: () => string;
export declare const getTsconfig: () => string;
export declare const getpackageJson: (dependencies?: Record<string, string>) => string;
