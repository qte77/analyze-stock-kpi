// Vitest config — kept minimal. Tests run against the pure-JS modules
// extracted out of ui/app.js into ui/lib/*.js (closes #131).
// The DOM-coupled app.js is not unit-tested; the lib/ split exists so
// the testable units don't carry DOM imports.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/demo/**/*.test.mjs"],
    environment: "node",
    reporters: process.env.CI ? ["verbose"] : ["default"],
  },
});
