// Frontend settings, read once from the environment (see .env.example).
// Mock mode is the default so the app runs with no backend.
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API !== "false";

// Shows a "Try the demo" button on the login screen (real mode). The server must also enable POST /auth/demo.
export const DEMO_LOGIN = process.env.NEXT_PUBLIC_DEMO_LOGIN === "true";
