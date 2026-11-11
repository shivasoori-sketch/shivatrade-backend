import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/kaaldrishti/thesis-card/",
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "main.jsx",
      output: {
        entryFileNames: "thesis-card.js",
        assetFileNames: "thesis-card.[ext]",
      },
    },
    cssCodeSplit: false,
  },
});
