import { ChatScreen } from "@/components/shell/chat-screen";

// Screen 6: the PayPal authorization window over the chat. `a` = agreement id.
export default async function PayPage({
  params,
  searchParams,
}: {
  params: Promise<{ chatId: string }>;
  searchParams: Promise<{ a?: string }>;
}) {
  const { chatId } = await params;
  const { a } = await searchParams;
  return (
    <ChatScreen
      key={`${chatId}-pay-${a ?? ""}`}
      chatId={chatId}
      phase="pay"
      agreementId={a}
    />
  );
}
