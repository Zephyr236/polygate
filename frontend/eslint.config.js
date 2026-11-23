/**
 * ESLint flat configuration for the polygate frontend.
 */

import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import jsdoc from "eslint-plugin-jsdoc";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "crap-report", "reports", "node_modules", "playwright-report", "eslint.config.js", ".dependency-cruiser.cjs"] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
      globals: { window: "readonly", document: "readonly", fetch: "readonly", ResizeObserver: "readonly" },
    },
    plugins: { "react-hooks": reactHooks, jsdoc },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/ban-ts-comment": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/consistent-type-imports": "error",
      "prefer-const": "error",
      eqeqeq: ["error", "always"],
      "no-console": "error",
      "jsdoc/require-jsdoc": [
        "error",
        {
          publicOnly: true,
          require: { FunctionDeclaration: true, MethodDefinition: true, ClassDeclaration: true, ArrowFunctionExpression: false },
          contexts: ["ExportNamedDeclaration > FunctionDeclaration", "ExportNamedDeclaration > VariableDeclaration"],
          checkConstructors: false,
        },
      ],
      "jsdoc/require-description": [
        "error",
        { contexts: ["any"], descriptionStyle: "body" },
      ],
      "jsdoc/check-values": "error",
    },
  },
  {
    files: ["*.config.ts", "e2e/**/*.ts"],
    rules: { "jsdoc/require-jsdoc": "off" },
  },
  {
    files: ["tests/**/*.{ts,tsx}"],
    rules: {
      "jsdoc/require-jsdoc": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/unbound-method": "off",
      "@typescript-eslint/require-await": "off",
    },
  },
  prettier,
);
