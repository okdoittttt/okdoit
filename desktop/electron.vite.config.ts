import { resolve } from "node:path";
import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";

/**
 * electron-vite 통합 설정.
 *
 * - main: Node.js 메인 프로세스. Electron API + Node 모듈 사용.
 * - preload: 격리된 컨텍스트 브릿지. 작은 surface 만 노출.
 * - renderer: React 앱. Chromium 안에서 실행되는 일반 웹.
 *
 * `externalizeDepsPlugin` 은 main/preload 빌드에서 node_modules 의존성을
 * 번들링하지 않고 require 로 두어 빌드 결과를 작게 유지한다(Electron 환경에서는
 * 어차피 node_modules 를 그대로 쓰므로 안전).
 */
export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: "out/main",
      rollupOptions: {
        input: { index: resolve(__dirname, "electron/main.ts") },
      },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: "out/preload",
      rollupOptions: {
        input: { index: resolve(__dirname, "electron/preload.ts") },
      },
    },
  },
  renderer: {
    root: resolve(__dirname, "src"),
    plugins: [react()],
    resolve: {
      alias: { "@": resolve(__dirname, "src") },
    },
    build: {
      outDir: "out/renderer",
      rollupOptions: {
        input: { index: resolve(__dirname, "src/index.html") },
      },
    },
  },
});
