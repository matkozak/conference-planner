// Separate from vite.config.ts on purpose: the Cloudflare plugin is
// incompatible with vitest's node environment, and these tests are plain Node.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["scripts/**/*.test.ts", "src/**/*.test.ts"],
  },
});
