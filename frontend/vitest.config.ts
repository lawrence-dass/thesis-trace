import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

/** Vitest, deliberately WITHOUT jsdom or React Testing Library.
 *
 *  Everything currently untested in this app is a pure function — rate and money
 *  formatting, list prose, and the band plot's geometry. Adding a DOM environment
 *  and a component-testing library would pull in three dependencies and CI time to
 *  cover nothing that exists untested today. When there is a component whose
 *  behaviour is worth mounting, that is its own decision; this config is the
 *  smallest thing that makes the existing logic testable.
 *
 *  `node` environment for the same reason: these tests touch no DOM at all.
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["app/**/*.test.ts", "app/**/*.test.tsx"],
    globals: false,
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./app", import.meta.url)),
    },
  },
});
