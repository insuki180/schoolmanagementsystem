"""Auth routes — login, logout, password change."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.dependencies import DBSession, get_current_user
from app.services.auth_service import authenticate_user, create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.config import get_settings
from sqlalchemy import select

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _wants_json(request: Request) -> bool:
    content_type = request.headers.get("content-type", "").lower()
    accept = request.headers.get("accept", "").lower()
    return "application/json" in content_type or "application/json" in accept


async def _read_login_payload(request: Request) -> tuple[str, str]:
    if _wants_json(request):
        payload = await request.json()
        return (payload.get("email", "") or "").strip(), payload.get("password", "") or ""

    form = await request.form()
    return (form.get("email", "") or "").strip(), form.get("password", "") or ""


async def _read_change_password_payload(request: Request) -> tuple[str, str, str]:
    if _wants_json(request):
        payload = await request.json()
        old_password = payload.get("oldPassword", "") or ""
        new_password = payload.get("newPassword", "") or ""
        confirm_password = payload.get("confirmPassword", new_password) or ""
        return old_password, new_password, confirm_password

    form = await request.form()
    return (
        form.get("current_password", "") or "",
        form.get("new_password", "") or "",
        form.get("confirm_password", "") or "",
    )


def _change_password_error_response(
    request: Request,
    current_user: User,
    error: str,
):
    if _wants_json(request):
        return JSONResponse({"detail": error}, status_code=400)

    return templates.TemplateResponse("auth/change_password.html", {
        "request": request,
        "user": current_user,
        "error": error,
        "success": None,
        "require_current_password": True,
    }, status_code=400)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page."""
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "error": None,
    })


@router.post("/login")
async def login(
    request: Request,
    db: DBSession,
):
    """Authenticate a user and return JSON or redirect based on request mode."""
    email, password = await _read_login_payload(request)
    user = await authenticate_user(db, email, password)
    if (
        not user
        and email == settings.SUPER_ADMIN_EMAIL
        and password == settings.SUPER_ADMIN_PASSWORD
    ):
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            safe_password = settings.SUPER_ADMIN_PASSWORD[:50]
            user = User(
                name=settings.SUPER_ADMIN_NAME,
                email=settings.SUPER_ADMIN_EMAIL,
                password_hash=hash_password(safe_password),
                role=UserRole.SUPER_ADMIN,
                must_change_password=False,
                is_active=True,
            )
            db.add(user)
            await db.flush()
        elif verify_password(settings.SUPER_ADMIN_PASSWORD[:50], user.password_hash):
            pass
        else:
            user = None
    if not user:
        if _wants_json(request):
            return JSONResponse({"detail": "Invalid email or password"}, status_code=401)
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid email or password",
        }, status_code=401)

    token = create_access_token({
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, 'value') else user.role,
        "school_id": user.school_id,
    })
    force_password_change = bool(
        getattr(user, "is_temp_password", False) or user.must_change_password
    )

    if _wants_json(request):
        response = JSONResponse({
            "token": token,
            "forcePasswordChange": force_password_change,
        })
    elif force_password_change:
        response = RedirectResponse(url="/change-password", status_code=303)
    else:
        response = RedirectResponse(url="/dashboard", status_code=303)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        max_age=60 * 60 * 8,  # 8 hours
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    """Clear JWT cookie and redirect to login."""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Render password change page."""
    return templates.TemplateResponse("auth/change_password.html", {
        "request": request,
        "user": current_user,
        "error": None,
        "success": None,
        "require_current_password": True,
    })


@router.post("/change-password")
async def change_password(
    request: Request,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Handle password change."""
    current_password, new_password, confirm_password = await _read_change_password_payload(request)

    if new_password != confirm_password:
        return _change_password_error_response(request, current_user, "Passwords do not match")

    if len(new_password) < 6:
        return _change_password_error_response(request, current_user, "Password must be at least 6 characters")

    if not current_password:
        return _change_password_error_response(request, current_user, "Current password is required")

    if not verify_password(current_password, current_user.password_hash):
        return _change_password_error_response(request, current_user, "Current password is incorrect")

    if verify_password(new_password, current_user.password_hash):
        return _change_password_error_response(
            request,
            current_user,
            "New password must be different from the current password",
        )

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.is_temp_password = False
    await db.flush()

    if _wants_json(request):
        return JSONResponse({"success": True, "forcePasswordChange": False})

    return RedirectResponse(url="/dashboard", status_code=303)
