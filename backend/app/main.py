from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import router as health_router
from app.api.unsubscribe import router as unsubscribe_router
from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.companies import router as companies_router
from app.api.v1.email_setups import router as email_setups_router
from app.api.v1.icp import router as icp_router
from app.api.v1.leads import router as leads_router
from app.api.v1.providers import router as providers_router
from app.api.v1.search import router as search_router
from app.api.v1.search_batches import router as search_batches_router
from app.api.v1.suppressions import router as suppressions_router
from app.api.v1.tags import router as tags_router
from app.api.v1.tracking import router as tracking_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.workspace_api_keys import router as workspace_api_keys_router
from app.api.v1.workspaces import router as workspaces_router
from app.core.config import get_settings
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.utils.db_errors import db_unavailable_payload, is_db_connectivity_error
from app.utils.logging import configure_logging, get_logger
from app.utils.metrics import PrometheusMiddleware

settings = get_settings()
configure_logging(debug=settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("app_startup", environment=settings.ENVIRONMENT)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(_request: Request, exc: SQLAlchemyError):
    if is_db_connectivity_error(exc):
        logger.warning("database_unavailable", error=str(exc))
        return JSONResponse(status_code=503, content={"detail": db_unavailable_payload(exc)})
    logger.exception("sqlalchemy_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": {"error": "database_error", "issue": db_unavailable_payload(exc)["issue"]}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    from fastapi import HTTPException as FastAPIHTTPException
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    # Let FastAPI/Starlette handle their own control-flow exceptions.
    if isinstance(exc, (FastAPIHTTPException, StarletteHTTPException, RequestValidationError)):
        raise exc

    if is_db_connectivity_error(exc):
        logger.warning("database_unavailable", error=str(exc))
        return JSONResponse(status_code=503, content={"detail": db_unavailable_payload(exc)})
    logger.exception("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": {"error": "internal_server_error", "issue": str(exc)[:800]}},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    # Production frontends / previews on Vercel (e.g. lead-generation-frontend-*.vercel.app)
    allow_origin_regex=r"https://([a-z0-9-]+\.)?vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(SecurityHeadersMiddleware, hsts=settings.ENVIRONMENT == "production")
app.add_middleware(RequestContextMiddleware)
app.add_middleware(PrometheusMiddleware)

app.include_router(health_router)
app.include_router(unsubscribe_router)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(workspaces_router, prefix=settings.API_V1_PREFIX)
app.include_router(companies_router, prefix=settings.API_V1_PREFIX)
app.include_router(icp_router, prefix=settings.API_V1_PREFIX)
app.include_router(leads_router, prefix=settings.API_V1_PREFIX)
app.include_router(providers_router, prefix=settings.API_V1_PREFIX)
app.include_router(search_router, prefix=settings.API_V1_PREFIX)
app.include_router(search_batches_router, prefix=settings.API_V1_PREFIX)
app.include_router(campaigns_router, prefix=settings.API_V1_PREFIX)
app.include_router(suppressions_router, prefix=settings.API_V1_PREFIX)
app.include_router(email_setups_router, prefix=settings.API_V1_PREFIX)
app.include_router(workspace_api_keys_router, prefix=settings.API_V1_PREFIX)
app.include_router(tags_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(webhooks_router, prefix=settings.API_V1_PREFIX)
app.include_router(tracking_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
