import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Polished screens waiting to be rewired to the real backend (specs/frontend-integration.md section 9, steps 4 to 9).
// They still import deleted mock code, so they are excluded here and in tsconfig.json. Remove an entry when its screen is ported.
const pendingShell = [
  "components/shell/agreement-chat.tsx",
  "components/shell/budget-card.tsx",
  "components/shell/budget-panel.tsx",
  "components/shell/result-chat.tsx",
  "components/shell/round2-chat.tsx",
  "components/shell/training-chat.tsx",
  "components/shell/verified-chat.tsx",
]

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([".next/**", "node_modules/**", "next-env.d.ts", "test-results/**", ...pendingShell]),
]);
