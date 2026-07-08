from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter(prefix="/admin", tags=["admin"])

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir) if os.path.exists(templates_dir) else None


@router.get("", response_class=HTMLResponse)
async def admin_index(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("<h1>Admin Dashboard</h1><p>Under construction.</p>")


@router.get("/health")
async def health():
    return {"status": "ok"}
