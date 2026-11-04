import { PayReturn } from "@/components/real/pay-return";
import { MockModeNotice } from "@/components/real/mock-notice";

// PayPal's return address (backend setting PAYPAL_RETURN_URL). Real mode only.
export default function PayReturnPage() {
  return (
    <MockModeNotice>
      <PayReturn />
    </MockModeNotice>
  );
}
