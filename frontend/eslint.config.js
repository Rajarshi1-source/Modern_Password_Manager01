import js from '@eslint/js';
import globals from 'globals';
import reactPlugin from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import securityPlugin from 'eslint-plugin-security';
import tseslint from 'typescript-eslint';

export default [
  // Ignore built output and coverage
  {
    ignores: ['dist/**', 'coverage/**', 'node_modules/**'],
  },

  // Base JS rules for all JS/JSX files
  {
    files: ['src/**/*.{js,jsx}'],
    ...js.configs.recommended,
    plugins: {
      react: reactPlugin,
      'react-hooks': reactHooks,
      security: securityPlugin,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        ...globals.browser,
        ...globals.es2020,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      ...reactPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...securityPlugin.configs.recommended.rules,
      // Relax a few rules that fire constantly in this codebase
      'react/prop-types': 'off',       // TypeScript will handle this
      'react/react-in-jsx-scope': 'off', // Not needed with React 17+ JSX transform
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'no-console': ['warn', { allow: ['warn', 'error', 'log'] }],
      // Security rules default to `error`; downgrade the noisy ones to
      // warnings so new issues surface in PRs without blocking the build.
      'security/detect-object-injection': 'warn',
      'security/detect-non-literal-fs-filename': 'warn',
      'security/detect-non-literal-regexp': 'warn',
    },
  },

  // TypeScript rules for new .ts/.tsx files only
  // This deliberately does NOT apply to .js files so existing code is unaffected
  {
    files: ['src/**/*.{ts,tsx}'],
    ...tseslint.configs.recommended[0],
    plugins: {
      '@typescript-eslint': tseslint.plugin,
      react: reactPlugin,
      'react-hooks': reactHooks,
      security: securityPlugin,
    },
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        project: './tsconfig.json',
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      ...reactPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...securityPlugin.configs.recommended.rules,
      'react/prop-types': 'off',
      'react/react-in-jsx-scope': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'security/detect-object-injection': 'warn',
      'security/detect-non-literal-fs-filename': 'warn',
      'security/detect-non-literal-regexp': 'warn',
    },
  },
];