import { WelcomeScreen } from "@/components/shell/welcome-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Welcome" };

export default function WelcomePage() {
  return <WelcomeScreen />;
}
