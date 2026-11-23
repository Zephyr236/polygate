/**
 * Vitest setup: jsdom matchers and browser API shims.
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

/** Minimal ResizeObserver shim required by chart components. */
class ResizeObserverShim {
  observe(): void {
    /* charts never assert observer callbacks in tests */
  }

  unobserve(): void {
    /* no-op */
  }

  disconnect(): void {
    /* no-op */
  }
}

globalThis.ResizeObserver = ResizeObserverShim;

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});
