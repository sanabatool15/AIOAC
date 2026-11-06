"use client";
import { RealFlow } from "@/components/real/real-flow";

// Route body for /c/[chatId]: one screen chosen from the project status (components/real until plan steps 5 to 9 land).
export function ChatScreen({ chatId }: { chatId: string }) {
  return <RealFlow projectId={chatId} />;
}
