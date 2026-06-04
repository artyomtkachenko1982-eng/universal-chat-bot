import os
import subprocess
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter()

TOKEN = settings.MANAGE_TOKEN
BASE_DIR = "/app"


class ExecRequest(BaseModel):
    token: str
    cmd: str


class ReadRequest(BaseModel):
    token: str
    path: str


class WriteRequest(BaseModel):
    token: str
    path: str
    content: str


def check_token(token: str):
    if token != TOKEN:
        raise HTTPException(403, "Неверный токен")


@router.post("/api/manage/exec")
async def run_cmd(req: ExecRequest):
    check_token(req.token)
    try:
        result = subprocess.run(req.cmd, shell=True, capture_output=True, text=True, cwd=BASE_DIR, timeout=30)
        return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout", "code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "code": -1}


@router.post("/api/manage/read")
async def read_file(req: ReadRequest):
    check_token(req.token)
    filepath = os.path.join(BASE_DIR, req.path.lstrip("/"))
    if not os.path.exists(filepath):
        raise HTTPException(404, "Файл не найден")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return {"content": content, "size": len(content)}


@router.post("/api/manage/write")
async def write_file(req: WriteRequest):
    check_token(req.token)
    filepath = os.path.join(BASE_DIR, req.path.lstrip("/"))
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(req.content)
    return {"status": "ok", "path": req.path, "size": len(req.content)}


@router.post("/api/manage/edit")
async def edit_file(req: WriteRequest):
    """Замена текста в файле. req.content = 'old_text|||new_text'"""
    check_token(req.token)
    filepath = os.path.join(BASE_DIR, req.path.lstrip("/"))
    if not os.path.exists(filepath):
        raise HTTPException(404, "Файл не найден")
    parts = req.content.split("|||")
    if len(parts) != 2:
        raise HTTPException(400, "Формат: old_text|||new_text")
    old, new = parts
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    if old not in content:
        raise HTTPException(400, "Старый текст не найден")
    content = content.replace(old, new, 1)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "ok", "path": req.path, "replaced": True}
