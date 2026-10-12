# -*- coding: utf-8 -*-
"""RepoSnipy 后端接口（FastAPI）。

启动：
    .venv\\Scripts\\python.exe -m uvicorn api.main:app --port 8000
接口文档：http://localhost:8000/docs
"""
from __future__ import annotations

import mimetypes
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api import engine
from api.schemas import IndexRequest, IndexResponse, MetaResponse, RepoCard, SearchResponse

# Windows 的注册表经常把 .js 登记成 text/plain，浏览器会拒绝执行 type="module"
# 脚本，页面直接白屏。必须在挂载静态目录之前强制修正 MIME 映射。
mimetypes.init()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("font/woff2", ".woff2")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

PLACEHOLDER = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>RepoSnipy API</title></head>
<body style="font-family:system-ui;background:#0b0f19;color:#e6edf7;padding:48px">
  <h1>RepoSnipy API 已启动</h1>
  <p>前端还没有构建。开发模式请在 frontend 目录执行 <code>npm run dev</code>（默认 http://localhost:5173）。</p>
  <p>接口文档：<a style="color:#5eead4" href="/docs">/docs</a></p>
</body></html>"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 索引在后台线程里载入，接口立即可用（前端会轮询 /api/meta 直到 ready）
    threading.Thread(target=engine.warmup, daemon=True).start()
    yield


app = FastAPI(
    title="RepoSnipy API",
    description="神经网络 Python 仓库检索服务",
    version="2.0.0",
    lifespan=lifespan,
)

# 开发模式下前端跑在 5173，需要放行跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _guard(callable_, *args, **kwargs):
    """把引擎里的异常翻译成合适的 HTTP 状态码。"""
    try:
        return callable_(*args, **kwargs)
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"索引中找不到仓库 {exc.args[0]}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/health", summary="健康检查")
def health():
    return {"status": "ok", "engine": engine.STATE["state"]}


@app.get("/api/meta", response_model=MetaResponse, summary="索引概览 / 初始化状态")
def meta():
    return engine.meta_payload()


@app.get("/api/repo", response_model=RepoCard, summary="查询单个仓库")
def repo(name: str = Query(..., description="owner/repo")):
    payload = _guard(engine.get_repo, name)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"{name} 尚未收录在索引中")
    return payload


@app.get("/api/search", response_model=SearchResponse, summary="相似仓库检索")
def search(
    name: str = Query(..., description="owner/repo"),
    mode: str = Query(
        engine.DEFAULT_MODE,
        description="domain（同领域，多通道融合）| code | doc | readme | requirement",
    ),
    limit: int = Query(10, ge=1, le=100, description="返回条数"),
):
    resolved = engine.resolve_mode(mode)
    query_doc = _guard(engine.get_repo, name)
    if query_doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"{name} 尚未收录在索引中，请先通过 /api/index 编码入库",
        )
    results = _guard(engine.search, name, resolved, limit)
    return {"name": name, "mode": resolved, "limit": limit, "query": query_doc, "results": results}


@app.post("/api/index", response_model=IndexResponse, summary="编码并写入一个新仓库")
def index_repo(payload: IndexRequest = Body(...)):
    encoded = _guard(engine.encode_repo, payload.name, payload.github_token)
    return _guard(engine.persist_repo, encoded)


if (FRONTEND_DIST / "index.html").exists():
    # 生产模式：直接托管 npm run build 产物
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def placeholder():
        return PLACEHOLDER
