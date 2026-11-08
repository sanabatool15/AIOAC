import { HomeScreen } from "@/components/shell/home-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "New project" };

// Signed-out visitors are redirected to /login by AppShell, so the app always starts at screen 1.
export default function Home() {
  return <HomeScreen />;
}
