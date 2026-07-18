"""Auth routes — Google sign-in, refresh, logout.

Per spec §10 and the auth design doc. ``POST /v1/auth/oauth/google`` replaces
the spec's literal ``/callback`` endpoint because the flow is client-driven
ID-token exchange.

Google exchange is limited per socket peer; refresh is limited per peer plus a
non-reversible token fingerprint. Redis failure returns 503 rather than silently
disabling the control.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from jobify_api.auth.service import AuthService, get_auth_service
from jobify_api.rate_limit import RateLimitExceededError, client_address

router = APIRouter(prefix="/v1/auth", tags=["auth"])


async def _enforce_auth_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    identity: str = "",
) -> None:
    key = f"{scope}:{client_address(request)}:{identity}"
    try:
        await request.app.state.rate_limiter.hit(key=key, limit=limit, window_seconds=60)
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="rate_limiter_unavailable",
        ) from exc


class GoogleSignInRequest(BaseModel):
    id_token: str = Field(..., min_length=1)


class SignInUser(BaseModel):
    id: UUID
    email: str
    role: str
    applicant_id: UUID
    is_new_user: bool


class SignInResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: SignInUser


@router.post(
    "/oauth/google",
    response_model=SignInResponse,
    status_code=status.HTTP_200_OK,
)
async def sign_in_with_google(
    request: Request,
    payload: GoogleSignInRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> SignInResponse:
    await _enforce_auth_limit(
        request,
        scope="google",
        limit=request.app.state.settings.auth_google_rate_limit_per_minute,
    )
    result = await service.sign_in_with_google(
        payload.id_token,
        request_id=request.state.request_id,
    )
    return SignInResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        user=SignInUser(
            id=result.user.id,
            email=result.user.email or "",
            role=result.user.role.value,
            applicant_id=result.applicant.id,
            is_new_user=result.is_new_user,
        ),
    )


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh_token(
    request: Request,
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> RefreshResponse:
    token_fingerprint = hashlib.sha256(payload.refresh_token.encode()).hexdigest()[:16]
    await _enforce_auth_limit(
        request,
        scope="refresh",
        limit=request.app.state.settings.auth_refresh_rate_limit_per_minute,
        identity=token_fingerprint,
    )
    result = await service.refresh(payload.refresh_token)
    return RefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
    )


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def logout(
    payload: LogoutRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> Response:
    await service.logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
