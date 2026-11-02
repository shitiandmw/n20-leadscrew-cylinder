import { defineConfig } from "vite";

export default defineConfig({
  build: {
    // The renderer is lazy-loaded; phone remotes never download Three.js or CAD.
    rollupOptions: { output: { manualChunks: { three: ["three"] } } },
  },
});
