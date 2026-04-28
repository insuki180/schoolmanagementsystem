"""Auth routes — login, logout, password change."""

from fastapi import APIRouter, Request, Depends, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.dependencies import DBSession, get_current_user
from app.services.auth_service import authenticate_user, create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.config import get_settings
from sqlalchemy import select

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


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
    email: str = Form(...),
    password: str = Form(...),
):
    """Authenticate user and set JWT cookie."""
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
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid email or password",
        }, status_code=401)

    # Create JWT token
    token = create_access_token({
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, 'value') else user.role,
        "school_id": user.school_id,
    })

    # Check if must change password
    if user.must_change_password:
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
    })


@router.post("/change-password")
async def change_password(
    request: Request,
    db: DBSession,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """Handle password change."""
    # Validate
    if new_password != confirm_password:
        return templates.TemplateResponse("auth/change_password.html", {
            "request": request,
            "user": current_user,
            "error": "Passwords do not match",
            "success": None,
        })

    if len(new_password) < 6:
        return templates.TemplateResponse("auth/change_password.html", {
            "request": request,
            "user": current_user,
            "error": "Password must be at least 6 characters",
            "success": None,
        })

    if not verify_password(current_password, current_user.password_hash):
        return templates.TemplateResponse("auth/change_password.html", {
            "request": request,
            "user": current_user,
            "error": "Current password is incorrect",
            "success": None,
        })

    # Update password
    from sqlalchemy import select as sel
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        result = await session.execute(sel(User).where(User.id == current_user.id))
        user = result.scalar_one()
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        await session.commit()

    return RedirectResponse(url="/dashboard", status_code=303)
