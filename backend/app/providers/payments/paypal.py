class PayPalProvider:
    """PayPal sandbox via Orders v2 + webhooks.

    TODO(human review): implement against the CURRENT PayPal docs. Do not guess
    endpoints, fields or event names (CLAUDE.md rule 6).
    """

    def create_order(self, amount_cents, job_id):
        raise NotImplementedError

    def capture_order(self, order_id):
        raise NotImplementedError

    def refund(self, capture_id, amount_cents):
        raise NotImplementedError

    def verify_webhook(self, headers, body):
        raise NotImplementedError
