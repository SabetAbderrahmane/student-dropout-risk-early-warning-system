from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import get_active_user_allow_password_change
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, PasswordChangeRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid credentials"}},
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        result = AuthService(db).authenticate(payload.username, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid username/email or password.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        must_change_password=result.user.must_change_password,
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_active_user_allow_password_change),
) -> User:
    return current_user


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_active_user_allow_password_change),
    db: Session = Depends(get_db),
) -> TokenResponse:
    result = AuthService(db).change_password(
        current_user,
        payload.current_password.get_secret_value(),
        payload.new_password.get_secret_value(),
    )
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        must_change_password=False,
    )
