"""Dashboard authentication. Google sign-in is the only way in.

The session token never appears in a response body: it goes out as an
HttpOnly cookie, so an XSS bug in the dashboard cannot read it.
"""

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_session_token
from app.db.models import Users
from app.schemas.auth import AuthResponse, GoogleLoginRequest, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: Users) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_session_token(user.id, user.email),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.auth_token_ttl_minutes * 60,
        path="/",
    )


@router.post("/google", response_model=AuthResponse)
def google_login(payload: GoogleLoginRequest, response: Response, db: DbSession) -> AuthResponse:
    """Sign in with a Google ID token. The first sign-in creates the account
    and its organization."""
    user = auth_service.login_with_google(db, id_token=payload.id_token)
    _set_session_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> Users:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Drop the cookie. There is no server-side session: the JWT stays valid
    until it expires for anyone holding a copy."""
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name, path="/", secure=settings.auth_cookie_secure, samesite=settings.auth_cookie_samesite
    )
