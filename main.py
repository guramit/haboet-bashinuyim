from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import webhook, scheduler_routes, users
from app.scheduler import start_scheduler

app = FastAPI(title="הבועט בשינויים", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(scheduler_routes.router)
app.include_router(users.router)


@app.on_event("startup")
async def startup_event():
    start_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}
