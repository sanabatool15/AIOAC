import { Suspense } from "react";
import { KeysScreen } from "@/components/shell/keys-screen";

export default function KeysPage() {
  return (
    <Suspense>
      <KeysScreen />
    </Suspense>
  );
}
