// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Compatibility shim: several tests were written against jest's API
// (jest.fn/mock/spyOn/useFakeTimers). `vi` is API-compatible, so aliasing it
// lets those tests run under vitest without rewriting each one.
if (typeof globalThis.jest === 'undefined') {
  globalThis.jest = vi;
}

// jsdom does not implement the canvas 2D context. Chart components (chart.js,
// custom visualizers) call getContext() on mount; stub it so they can render
// in tests. Tests assert on surrounding DOM, not on pixel output.
if (typeof HTMLCanvasElement !== 'undefined') {
  HTMLCanvasElement.prototype.getContext = () => null;
}

// jsdom does not implement matchMedia. preferencesService.applyTheme() (on
// import) and anything reading prefers-color-scheme / prefers-reduced-motion
// (e.g. framer-motion's useReducedMotion) call it; provide a minimal stub so
// those modules load and render in tests.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
