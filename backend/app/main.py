from fastapi import FastAPI

from app.errors import ApiError, api_error_handler, internal_error_handler
from app.routes import webhook

app = FastAPI(title="Nexora WhatsApp Menu Bot")

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, internal_error_handler)

app.include_router(webhook.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
