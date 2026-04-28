"""Seed script — create Super Admin user and a demo school."""

import asyncio
from app.database import engine, Base, AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.school import School
from app.services.auth_service import hash_password
from app.config import get_settings
from sqlalchemy import select

settings = get_settings()


async def seed():
    """Create initial data: Super Admin + demo school."""
    # Import all models
    import app.models  # noqa: F401


    async with AsyncSessionLocal() as db:
        # Check if Super Admin exists
        result = await db.execute(
            select(User).where(User.email == settings.SUPER_ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Super Admin already exists: {settings.SUPER_ADMIN_EMAIL}")
        else:
            admin = User(
                name=settings.SUPER_ADMIN_NAME,
                email=settings.SUPER_ADMIN_EMAIL,
                password_hash=hash_password(settings.SUPER_ADMIN_PASSWORD),
                role=UserRole.SUPER_ADMIN,
                must_change_password=False,
                is_active=True,
            )
            db.add(admin)
            print(f"Created Super Admin: {settings.SUPER_ADMIN_EMAIL}")

        # Create demo school if none exists
        result = await db.execute(select(School))
        schools = result.scalars().all()
        if not schools:
            school = School(
                name="Demo School",
                address="123 Education Street",
                phone="555-0100",
            )
            db.add(school)
            print("Created Demo School")

        await db.commit()
        print("Seed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
