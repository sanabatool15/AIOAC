class PayPalProvider:
    """PayPal sandbox provider.

    TODO(human review): implement against the CURRENT PayPal docs and the PayPal
    toolkit skill. Do not guess endpoints, fields or event names (CLAUDE.md rule 6).
    parse_webhook must map PayPal's capture-completed event to PaymentEvent(kind="capture_completed").
    """

    def create_order(self, amount_cents, project_id):
        raise NotImplementedError

    def capture_order(self, order_id):
        raise NotImplementedError

    def refund(self, capture_id, amount_cents):
        raise NotImplementedError

    def verify_webhook(self, headers, body):
        raise NotImplementedError

    def parse_webhook(self, body):
        raise NotImplementedError
