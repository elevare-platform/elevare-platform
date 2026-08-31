from enum import Enum


class PlanInterval(str, Enum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class SubscriptionStatus(str, Enum):
    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentPurpose(str, Enum):
    SUBSCRIPTION_INITIAL = "SUBSCRIPTION_INITIAL"
    SUBSCRIPTION_RENEWAL = "SUBSCRIPTION_RENEWAL"
    CREDIT_TOPUP = "CREDIT_TOPUP"
    ADMIN_COMP = "ADMIN_COMP"


class PaymentProvider(str, Enum):
    PAYSTACK = "PAYSTACK"
