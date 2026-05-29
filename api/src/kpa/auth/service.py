"""AuthService — orchestrates sign-in, refresh, and logout.

Per-request: built by :func:`get_auth_service` over the request's AsyncSession,
the app-scoped Google verifier, and Settings. Service methods raise
``HTTPException`` directly (matching the codebase's existing pattern in
``routes/resumes.py``); routes are thin pass-throughs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.google_verifier import (
    GoogleClaims,
    GoogleIdTokenVerifier,
    GoogleJwksUnavailableError,
    InvalidGoogleTokenError,
    get_google_verifier,
)
from kpa.auth.tokens import (
    mint_access_token,
    mint_refresh_token,
    sha256_token_hash,
)
from kpa.consent import seed_default_consents
from kpa.db.models import (
    Applicant,
    OAuthIdentity,
    OAuthProvider,
    RefreshToken,
    User,
    UserRole,
)
from kpa.db.session import get_session
from kpa.settings import Settings

_log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SignInResult:
    user: User
    applicant: Applicant
    access_token: str
    refresh_token: str
    expires_in: int
    is_new_user: bool


@dataclass(frozen=True)
class RefreshResult:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        verifier: GoogleIdTokenVerifier,
        settings: Settings,
    ) -> None:
        self._session = session
        self._verifier = verifier
        self._settings = settings

    async def sign_in_with_google(
        self, id_token: str, *, request_id: str | None = None
    ) -> SignInResult:
        try:
            claims = await self._verifier.verify(id_token)
        except InvalidGoogleTokenError as exc:
            raise HTTPException(401, "invalid_google_token") from exc
        except GoogleJwksUnavailableError as exc:
            raise HTTPException(503, "google_jwks_unavailable") from exc

        if self._settings.auth_require_email_verified and not claims.email_verified:
            raise HTTPException(401, "email_not_verified")

        user, applicant, is_new_user = await self._upsert_identity(claims, request_id=request_id)

        access = mint_access_token(
            user_id=user.id,
            role=user.role.value,
            secret=self._settings.jwt_secret,
            ttl_seconds=self._settings.jwt_access_ttl_seconds,
        )
        refresh = await self._issue_refresh(user_id=user.id, family_id=uuid4())
        await self._session.commit()

        _log.info(
            "auth.signin",
            user_id=str(user.id),
            is_new_user=is_new_user,
            provider="google",
        )
        return SignInResult(
            user=user,
            applicant=applicant,
            access_token=access,
            refresh_token=refresh,
            expires_in=self._settings.jwt_access_ttl_seconds,
            is_new_user=is_new_user,
        )

    async def _upsert_identity(
        self, claims: GoogleClaims, *, request_id: str | None = None
    ) -> tuple[User, Applicant, bool]:
        """Return (user, applicant, is_new_user) for the given Google claims."""
        existing_ident = (
            await self._session.execute(
                select(OAuthIdentity).where(
                    OAuthIdentity.provider == OAuthProvider.GOOGLE,
                    OAuthIdentity.provider_subject == claims.sub,
                    OAuthIdentity.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if existing_ident is not None:
            user = await self._session.get(User, existing_ident.user_id)
            if user is None or user.deleted_at is not None:  # FK + filter invariant
                raise HTTPException(500, "identity_user_inconsistency")
            user.email = claims.email
            existing_ident.last_seen_at = datetime.now(UTC)
            applicant = (
                await self._session.execute(select(Applicant).where(Applicant.user_id == user.id))
            ).scalar_one()
            await self._session.flush()
            return user, applicant, False

        # New identity. Email collision check first.
        collision = (
            await self._session.execute(
                select(User).where(User.email == claims.email, User.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if collision is not None:
            raise HTTPException(409, "email_belongs_to_other_user")

        user = User(
            email=claims.email,
            phone=None,
            role=UserRole.APPLICANT,
            mfa_enabled=False,
        )
        self._session.add(user)
        await self._session.flush()  # populates user.id

        applicant = Applicant(
            user_id=user.id,
            full_name=claims.name or claims.email.split("@", 1)[0],
        )
        self._session.add(applicant)

        identity = OAuthIdentity(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_subject=claims.sub,
            email_at_link=claims.email,
        )
        self._session.add(identity)
        await self._session.flush()

        # Seed default consents in the same txn as user creation.
        await seed_default_consents(
            self._session,
            user=user,
            request_id=request_id,
        )

        return user, applicant, True

    async def _issue_refresh(self, *, user_id: UUID, family_id: UUID) -> str:
        """Mint + persist a refresh token. Returns the opaque string."""
        token = mint_refresh_token()
        now = datetime.now(UTC)
        row = RefreshToken(
            user_id=user_id,
            family_id=family_id,
            token_hash=sha256_token_hash(token),
            issued_at=now,
            expires_at=now + timedelta(seconds=self._settings.jwt_refresh_ttl_seconds),
        )
        self._session.add(row)
        await self._session.flush()
        return token

    async def refresh(self, presented_token: str) -> RefreshResult:
        token_hash = sha256_token_hash(presented_token)

        # Lock the row to serialize concurrent calls on the same token.
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )
        row: RefreshToken | None = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(401, "invalid_refresh")

        if row.revoked_at is not None:
            # REUSE detected — revoke the whole family.
            await self._revoke_family(row.family_id, reason="reuse_detected")
            await self._session.commit()
            raise HTTPException(401, "token_reused")

        if row.expires_at <= datetime.now(UTC):
            raise HTTPException(401, "expired_refresh")

        # Happy path: rotate.
        new_token = mint_refresh_token()
        now = datetime.now(UTC)
        new_row = RefreshToken(
            user_id=row.user_id,
            family_id=row.family_id,
            token_hash=sha256_token_hash(new_token),
            issued_at=now,
            expires_at=now + timedelta(seconds=self._settings.jwt_refresh_ttl_seconds),
        )
        self._session.add(new_row)
        await self._session.flush()

        row.replaced_by_id = new_row.id
        row.revoked_at = now
        row.revocation_reason = "rotated"
        row.last_used_at = now
        await self._session.flush()

        user = await self._session.get(User, row.user_id)
        if user is None or user.deleted_at is not None:
            raise HTTPException(401, "user_not_found")
        access = mint_access_token(
            user_id=user.id,
            role=user.role.value,
            secret=self._settings.jwt_secret,
            ttl_seconds=self._settings.jwt_access_ttl_seconds,
        )

        await self._session.commit()
        return RefreshResult(
            access_token=access,
            refresh_token=new_token,
            expires_in=self._settings.jwt_access_ttl_seconds,
        )

    async def logout(self, presented_token: str) -> None:
        """Revoke the presented refresh token. Idempotent: silent on unknown."""
        token_hash = sha256_token_hash(presented_token)
        row = (
            await self._session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return  # No oracle on token existence.

        row.revoked_at = datetime.now(UTC)
        row.revocation_reason = "logout"
        await self._session.flush()
        await self._session.commit()

    async def _revoke_family(self, family_id: UUID, *, reason: str) -> None:
        """Revoke all currently-unrevoked rows in the family.

        Uses a bulk UPDATE so the WHERE clause is re-evaluated atomically per
        row under Postgres's READ COMMITTED + EvalPlanQual semantics — a
        concurrent legitimate rotation in this family is correctly waited on
        and the resulting new row is also caught and revoked.

        Caller is responsible for committing.
        """
        from sqlalchemy import update  # local import to keep top-of-file tidy

        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC), revocation_reason=reason)
        )
        await self._session.flush()


def get_auth_service(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    verifier: GoogleIdTokenVerifier = Depends(get_google_verifier),  # noqa: B008
) -> AuthService:
    return AuthService(
        session=session,
        verifier=verifier,
        settings=request.app.state.settings,
    )
