"""Account list extraction API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from i4g.services.account_list import AccountListRequest, AccountListResult, AccountListService
from i4g.settings import Settings, get_settings

router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_account_list_service() -> AccountListService:
    """Dependency provider returning the shared AccountListService instance."""

    return AccountListService()


def require_account_list_key(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate the account-list API key header, leveraging nested settings."""

    config = settings.account_list
    if not config.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Account list disabled")
    if not config.require_api_key:
        return
    expected_key = config.api_key or settings.api.key
    if not expected_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="API key not configured")
    header_name = config.header_name or "X-ACCOUNTLIST-KEY"
    provided_key = request.headers.get(header_name)
    if not provided_key and header_name.lower() != "x-api-key":
        provided_key = request.headers.get("X-API-KEY")
    if provided_key != expected_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid account list API key")


@router.post(
    "/extract",
    response_model=AccountListResult,
    summary="Extract financial account indicators from analyst data",
)
def extract_account_list(
    payload: AccountListRequest,
    _: None = Depends(require_account_list_key),
    service: AccountListService = Depends(get_account_list_service),
    settings: Settings = Depends(get_settings),
) -> AccountListResult:
    """Execute the account-list workflow and return structured indicators."""

    max_top_k = settings.account_list.max_top_k
    if payload.top_k > max_top_k:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"top_k cannot exceed {max_top_k}",
        )
    return service.run(payload)
