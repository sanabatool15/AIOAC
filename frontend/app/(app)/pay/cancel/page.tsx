import { PayCancel } from "@/components/real/pay-return";
import { MockModeNotice } from "@/components/real/mock-notice";

// PayPal's cancel address (backend setting PAYPAL_CANCEL_URL). Real mode only.
export default function PayCancelPage() {
  return (
    <MockModeNotice>
      <PayCancel />
    </MockModeNotice>
  );
}
