from ...config import settings
from .mock import MockPaymentProvider


def get_payment_provider():
    if settings.payment_provider == "paypal":
        from .paypal import PayPalProvider

        return PayPalProvider()
    return MockPaymentProvider()
