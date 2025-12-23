from .contractor import (
    ContractorAccount,
    ContractorAccountUpdate,
    ContractorBusinessDetails,
    ContractorBusinessDetailsUpdate,
    ContractorLicenseInfo,
    ContractorLicenseInfoUpdate,
    ContractorLocationInfo,
    ContractorLocationInfoUpdate,
    ContractorProfile,
    ContractorStep1,
    ContractorStep2,
    ContractorStep3,
    ContractorStep4,
    ContractorStepResponse,
    ContractorTradeInfo,
    ContractorTradeInfoUpdate,
)
from .subscription import (
    BulkUploadResponse,
    DashboardResponse,
    FilterRequest,
    JobBase,
    JobCreate,
    JobDetailResponse,
    JobResponse,
    MatchedJobSummary,
    PaginatedJobResponse,
    SubscriberResponse,
    SubscriptionResponse,
    UnlockedLeadResponse,
)
from .supplier import (
    SupplierAccount,
    SupplierAccountUpdate,
    SupplierBusinessDetails,
    SupplierBusinessDetailsUpdate,
    SupplierCapabilities,
    SupplierCapabilitiesUpdate,
    SupplierDeliveryInfo,
    SupplierDeliveryInfoUpdate,
    SupplierProducts,
    SupplierProductsUpdate,
    SupplierProfile,
    SupplierStep1,
    SupplierStep2,
    SupplierStep3,
    SupplierStep4,
    SupplierStepResponse,
)
from .token import Token, TokenData
from .user import (
    PasswordResetConfirm,
    PasswordResetRequest,
    RoleUpdate,
    RoleUpdateResponse,
    User,
    UserCreate,
    UserLogin,
    VerifyEmail,
)

__all__ = [
    "UserCreate",
    "UserLogin",
    "VerifyEmail",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "RoleUpdate",
    "RoleUpdateResponse",
    "User",
    "Token",
    "TokenData",
    "ContractorStep1",
    "ContractorStep2",
    "ContractorStep3",
    "ContractorStep4",
    "ContractorStepResponse",
    "ContractorProfile",
    "ContractorAccount",
    "ContractorAccountUpdate",
    "ContractorBusinessDetails",
    "ContractorBusinessDetailsUpdate",
    "ContractorLicenseInfo",
    "ContractorLicenseInfoUpdate",
    "ContractorTradeInfo",
    "ContractorTradeInfoUpdate",
    "ContractorLocationInfo",
    "ContractorLocationInfoUpdate",
    "SupplierStep1",
    "SupplierStep2",
    "SupplierStep3",
    "SupplierStep4",
    "SupplierStepResponse",
    "SupplierProfile",
    "SupplierAccount",
    "SupplierAccountUpdate",
    "SupplierBusinessDetails",
    "SupplierBusinessDetailsUpdate",
    "SupplierDeliveryInfo",
    "SupplierDeliveryInfoUpdate",
    "SupplierCapabilities",
    "SupplierCapabilitiesUpdate",
    "SubscriptionResponse",
    "SubscriberResponse",
    "JobBase",
    "JobCreate",
    "JobResponse",
    "JobDetailResponse",
    "MatchedJobSummary",
    "PaginatedJobResponse",
    "UnlockedLeadResponse",
    "DashboardResponse",
    "FilterRequest",
    "BulkUploadResponse",
]


def __getattr__(name: str):
    """Lazy-import schema attributes from submodules to avoid circular imports.

    Attempts to import the requested name from known submodules and caches
    the result on the package namespace.
    """
    import importlib

    submodules = ["supplier", "contractor", "subscription", "user", "token"]
    for mod_name in submodules:
        try:
            mod = importlib.import_module(f".{mod_name}", __package__)
        except Exception:
            continue
        if hasattr(mod, name):
            val = getattr(mod, name)
            globals()[name] = val
            return val
    raise AttributeError(f"module {__name__} has no attribute {name}")
