"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import logging
from app.database import engine, Base
from app.routers import auth, dashboard, schools, users, attendance, notifications, exams, marks, classes


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await wait_for_db(engine)
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
app.include_router(attendance.router)
app.include_router(notifications.router)
app.include_router(exams.router)
app.include_router(marks.router)
app.include_router(classes.router)


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
