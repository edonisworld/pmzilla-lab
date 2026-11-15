// Configuration of the end-to-end pass (mothra-slices D12, task 8.2): one browser, one worker, the page opened at the address of the Mothra
// server (MOTHRA_E2E_URL, set by tools/dbtest.sh --e2e), never at the Vite development server. Nothing is downloaded: the browsers are
// installed once by the author. The results folder lives under node_modules, which Git ignores, so the pass leaves the tree clean.
export default {
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "line",
  outputDir: "../../mothra/node_modules/.cache/e2e-results",
  use: {
    baseURL: process.env.MOTHRA_E2E_URL,
    locale: "en-US",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
};
