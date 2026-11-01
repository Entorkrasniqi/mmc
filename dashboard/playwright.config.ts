import { defineConfig, devices } from "@playwright/test";

// The tests run against the REAL stack: tools/e2e_stack.py starts PostgreSQL (docker compose), the simulator, the ground station,
// the API and the dashboard, and stops them again. Nothing is mocked. It needs Docker and the Python environment of the project
// (override the interpreter with MINISAT_PYTHON).
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "./test-results",
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `${process.env.MINISAT_PYTHON ?? ".venv/bin/python"} tools/e2e_stack.py --speedup 10`,
    cwd: "..",
    url: "http://127.0.0.1:5173",
    timeout: 300_000,
    reuseExistingServer: !process.env.CI,
    // the stack must get the chance to stop its services and remove its database (the default is SIGKILL)
    gracefulShutdown: { signal: "SIGTERM", timeout: 30_000 },
  },
});
