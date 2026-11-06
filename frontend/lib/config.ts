// Frontend settings, read once from the environment (see .env.example).
// The app always talks to the real backend.
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

// Shows a "Try the demo" button on the login screen. The server must also enable POST /auth/demo.
export const DEMO_LOGIN = process.env.NEXT_PUBLIC_DEMO_LOGIN === "true";
