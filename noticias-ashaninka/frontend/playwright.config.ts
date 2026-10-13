import { defineConfig } from "@playwright/test";

// Pruebas E2E en Chromium real. El servidor (scripts/e2e_server.py) crea datos deterministas con el
// motor `fake` y sirve la PWA compilada (frontend/dist) en el mismo origen que /static y /api.
const PORT = Number(process.env.E2E_PORT ?? 8765);
// Fase 5: segundo servidor con el material del experimento (BD propia, 4 noticias «revisadas»)
const PORT_EXP = PORT + 1;
const GPU = { launchOptions: { args: ["--use-angle=d3d11", "--ignore-gpu-blocklist"] } };

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 420, height: 900 },
  },
  // Tres perfiles de Chromium, como en la degradación de la Fase 3: con GPU del equipo, sin WebGL
  // y con renderizado por software (SwiftShader).
  projects: [
    {
      name: "gpu",
      testIgnore: /avatar-(sin-webgl|software)|experiment\.spec/,
      use: GPU,
    },
    {
      name: "experimento",
      testMatch: /experiment\.spec/,
      use: { ...GPU, baseURL: `http://127.0.0.1:${PORT_EXP}` },
    },
    {
      name: "sin-webgl",
      testMatch: /avatar-sin-webgl/,
      use: { launchOptions: { args: ["--disable-3d-apis", "--disable-gpu"] } },
    },
    {
      name: "software",
      testMatch: /avatar-software/,
      use: { launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] } },
    },
  ],
  webServer: [
    {
      command: `uv run python scripts/e2e_server.py --port ${PORT}`,
      cwd: "..",
      url: `http://127.0.0.1:${PORT}/api/health`,
      timeout: 180_000,
      reuseExistingServer: false,
    },
    {
      command: `uv run python scripts/e2e_server.py --port ${PORT_EXP} --experimento`,
      cwd: "..",
      url: `http://127.0.0.1:${PORT_EXP}/api/health`,
      timeout: 180_000,
      reuseExistingServer: false,
    },
  ],
});
