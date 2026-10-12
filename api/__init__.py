# -*- coding: utf-8 -*-
"""RepoSnipy 后端接口层（FastAPI）。

对外提供索引概览、仓库查询、相似检索与编码入库四组接口，
真正的检索逻辑都在 engine.py 里。
"""

__all__ = ["main"]
