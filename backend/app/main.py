from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware import RateLimitMiddleware, CSRFMiddleware, SecurityHeadersMiddleware, HTTPSRedirectMiddleware
from app.routers import auth, profile, capsules, notifications
from app.errors import register_error_handlers

app = FastAPI(
    title="TimeLock API",
    description="AI Powered Digital Time Capsule",
    version="1.0.0"
)

# Global error handlers
register_error_handlers(app)

# Middleware (outermost first — execution order is bottom-up in Starlette)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Remaining"],
)

# Routers
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(capsules.router)
app.include_router(capsules.public_router)
app.include_router(notifications.router)

@app.get("/")
async def root():
    return {"message": "TimeLock API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
