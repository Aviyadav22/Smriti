import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rolldownOptions: {
      output: {
        manualChunks(id: string) {
          if (
            id.includes("node_modules/three/") ||
            id.includes("node_modules/@react-three/")
          ) {
            return "three";
          }
        },
      },
    },
  },
});
