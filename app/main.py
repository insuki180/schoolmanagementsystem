"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import logging
from sqlalchemy import text
from app.database import engine, Base
from app.routers import auth, dashboard, schools, users, attendance, notifications, exams, marks, classes, student_imports, students


# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
import asyncio

async def wait_for_db(engine):
    logger.info("Waiting for database connection...")

    for i in range(15):  # ~45 seconds total
        try:
            async with engine.begin() as conn:
                await conn.run_sync(lambda conn: None)

            logger.info("✅ Database connection established.")
            return True

        except Exception as e:
            logger.warning(f"⏳ DB retry {i+1}/15... {str(e)}")
            await asyncio.sleep(3)

    logger.error("⚠️ Database still not ready, continuing app startup...")


async def ensure_school_logo_column(engine):
    """Keep the schools table compatible with the logo feature."""
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "ALTER TABLE schools "
                    "ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500)"
                )
            )
    except Exception as exc:
        logger.warning("Could not verify schools.logo_url column: %s", exc)


async def ensure_academic_control_schema(engine):
    """Keep the academic permission tables compatible on existing deployments."""
    statements = [
        (
            "ALTER TABLE classes "
            "ADD COLUMN IF NOT EXISTS class_teacher_id INTEGER REFERENCES users(id)"
        ),
        (
            "CREATE TABLE IF NOT EXISTS class_subjects ("
            "id SERIAL PRIMARY KEY, "
            "class_id INTEGER NOT NULL REFERENCES classes(id), "
            "subject_id INTEGER NOT NULL REFERENCES subjects(id), "
            "teacher_id INTEGER NOT NULL REFERENCES users(id))"
        ),
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_class_subject_assignment_idx "
            "ON class_subjects (class_id, subject_id)"
        ),
        (
            "CREATE TABLE IF NOT EXISTS absence_responses ("
            "id SERIAL PRIMARY KEY, "
            "student_id INTEGER NOT NULL REFERENCES students(id), "
            "date DATE NOT NULL, "
            "message TEXT NOT NULL, "
            "is_read BOOLEAN NOT NULL DEFAULT TRUE, "
            "created_by_parent INTEGER NOT NULL REFERENCES users(id), "
            "leave_days INTEGER NULL, "
            "created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW())"
        ),
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_absence_response_student_date_idx "
            "ON absence_responses (student_id, date)"
        ),
    ]
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    except Exception as exc:
        logger.warning("Could not verify academic control schema: %s", exc)


async def ensure_parent_contact_schema(engine):
    """Keep parent contact/profile columns compatible on existing deployments."""
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20)",
        "UPDATE users SET phone_number = REGEXP_REPLACE(COALESCE(phone, ''), '\\D', '', 'g') WHERE phone_number IS NULL AND phone IS NOT NULL",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS blood_group VARCHAR(20)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS address TEXT",
    ]
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    except Exception as exc:
        logger.warning("Could not verify parent contact schema: %s", exc)


async def ensure_notification_student_target_schema(engine):
    """Keep personal student notifications compatible on existing deployments."""
    statements = [
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS target_student_id INTEGER REFERENCES students(id)",
    ]
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    except Exception as exc:
        logger.warning("Could not verify personal notification schema: %s", exc)


async def ensure_temp_password_schema(engine):
    """Keep temporary-password state compatible on existing deployments."""
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_temp_password BOOLEAN DEFAULT FALSE",
        "UPDATE users SET is_temp_password = TRUE WHERE must_change_password = TRUE AND is_temp_password = FALSE",
    ]
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    except Exception as exc:
        logger.warning("Could not verify temporary password schema: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await wait_for_db(engine)
    await ensure_school_logo_column(engine)
    await ensure_academic_control_schema(engine)
    await ensure_parent_contact_schema(engine)
    await ensure_notification_student_target_schema(engine)
    await ensure_temp_password_schema(engine)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="School Management System",
    description="Multi-role school management web application",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for deployment orchestration (e.g. Render)."""
    return {"status": "ok"}

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(schools.router)
app.include_router(users.router)
app.include_router(users.management_router)
app.include_router(attendance.router)
app.include_router(notifications.router)
app.include_router(exams.router)
app.include_router(marks.router)
app.include_router(classes.router)
app.include_router(student_imports.router)
app.include_router(students.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Redirect to login on auth errors, show error otherwise."""
    if hasattr(exc, 'status_code') and exc.status_code == 303:
        return RedirectResponse(url=exc.headers.get("Location", "/login"), status_code=303)
    # For development, re-raise; in production, show error page
    raise exc

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
