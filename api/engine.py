# -*- coding: utf-8 -*-
"""RepoSnipy 检索引擎。

检索思路：不再使用四段拼接的 3072 维仓库级向量（那会把各通道的权重交给
向量范数决定），而是对四个通道分别做预处理，再按权重融合打分。

每个通道的预处理（索引载入时对全库算一次）：
    1. 减去全库均值向量
    2. 去掉方差最大的前 DROP_COMPONENTS 个主方向
    3. 逐行 L2 归一化
这三步是为了消除 mean-pooled 向量的"各向异性"：不加处理时，两个毫不相干
的仓库 README 余弦也有 0.49，真正有区分度的信号被公共偏置盖住了。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 模型放在项目内部，整个文件夹可以独立拷走运行
MODELS_DIR = Path(os.environ.get("REPOSNIPY_MODELS_DIR") or (PROJECT_ROOT / "models"))

# 数据集：developing（默认）或 product
DATASET = os.environ.get("REPOSNIPY_DATASET", "developing").strip().lower()
_SUFFIX = "" if DATASET == "product" else "_developing"
INDEX_PATH = PROJECT_ROOT / "data" / f"index{_SUFFIX}.bin"

_REPOSIM4PY_LOCAL = MODELS_DIR / "RepoSim4Py"
REPOSIM4PY_MODEL_PATH = (
    str(_REPOSIM4PY_LOCAL) if _REPOSIM4PY_LOCAL.exists() else "Henry65/RepoSim4Py"
)

# 四个检索通道：key -> RepoDoc 字段名
CHANNELS: Dict[str, str] = {
    "code": "code_embedding",
    "doc": "doc_embedding",
    "readme": "readme_embedding",
    "requirement": "requirement_embedding",
}
CHANNEL_KEYS = list(CHANNELS)

# 去掉前几个主方向。"8" 是在留出集上扫出来的经验值（试过 1/2/4/8 与完全白化），
# 2~8 之间差别不大，但不能全部去掉（白化会放大噪声方向，实测更差）。
DROP_COMPONENTS = int(os.environ.get("REPOSNIPY_DROP_COMPONENTS", "8"))

# 「同领域」融合权重（顺序：code / doc / readme / requirement）。
# 默认值来自需求方的设定：领域是"描述层面"的概念，所以重心放在 readme 与 doc。
# 实测这组权重与 code 重权重（0.60/0.00/0.30/0.10）的差异在统计上不显著。
# 想换可以改这里，或设环境变量 REPOSNIPY_DOMAIN_WEIGHTS="0.2,0.35,0.45,0"
_DEFAULT_WEIGHTS = [0.20, 0.35, 0.45, 0.00]
_env_weights = os.environ.get("REPOSNIPY_DOMAIN_WEIGHTS", "").strip()
if _env_weights:
    try:
        _parsed = [float(x) for x in _env_weights.split(",")]
        if len(_parsed) == len(CHANNEL_KEYS) and sum(_parsed) > 0:
            _DEFAULT_WEIGHTS = _parsed
    except ValueError:
        pass
DOMAIN_WEIGHTS: Dict[str, float] = dict(zip(CHANNEL_KEYS, _DEFAULT_WEIGHTS))

DEFAULT_MODE = "domain"

# 首页展示的示例仓库（只有确实在索引里才会返回）
CURATED_SAMPLES = [
    "numpy/numpy",
    "psf/requests",
    "django/django",
    "pytorch/pytorch",
    "huggingface/transformers",
    "tiangolo/fastapi",
    "pallets/flask",
    "scikit-learn/scikit-learn",
]

_LOCK = threading.RLock()

STATE: Dict[str, Any] = {
    "state": "idle",  # idle | loading | ready | error
    "message": "等待初始化",
    "error": None,
    "loaded_at": None,
    "load_seconds": None,
}

_RES: Dict[str, Any] = {
    "index": None,
    "docs": None,
    "by_name": None,
    "features": None,  # channel -> {"matrix": 归一化后的全库向量, "mean", "proj", "mask"}
    "pipeline": None,
}


def get_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _preprocess(matrix, mask) -> Tuple[Any, Any, Any]:
    """去均值 -> 去掉前 DROP_COMPONENTS 个主方向 -> 逐行归一化。

    返回 (归一化后的矩阵, 均值向量, 投影矩阵)，后两者用于给新仓库做同样的变换。
    """
    import numpy as np

    sub = matrix[mask]
    mean = sub.mean(axis=0, keepdims=True)
    centered = sub - mean
    cov = centered.T @ centered / max(len(sub) - 1, 1)
    values, vectors = np.linalg.eigh(cov.astype(np.float64))
    vectors = vectors[:, np.argsort(-values)]
    keep = np.ones(vectors.shape[1], dtype=np.float64)
    keep[: min(DROP_COMPONENTS, len(keep))] = 0.0
    projection = ((vectors * keep) @ vectors.T).astype(np.float32)

    out = matrix.copy()
    out[mask] = centered @ projection
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    out = out / np.maximum(norms, 1e-9)
    out[~mask] = 0.0
    return out, mean.astype(np.float32), projection


def _transform_one(vector, mean, projection):
    """对新仓库的向量施加与全库一致的变换。"""
    import numpy as np

    arr = np.asarray(vector, dtype=np.float32).reshape(1, -1) - mean
    arr = arr @ projection
    norm = float(np.linalg.norm(arr))
    return (arr / norm if norm > 1e-9 else arr).reshape(-1)


def _load_index() -> None:
    import numpy as np
    from docarray.index import InMemoryExactNNIndex

    from common.repo_doc import RepoDoc

    index = InMemoryExactNNIndex[RepoDoc](index_file_path=INDEX_PATH)

    # 索引里有少量重名仓库（如 microsoft/0xDeCA10B），这里按名字去重
    by_name: Dict[str, Any] = {}
    unique_docs = []
    for doc in index._docs:
        if doc.name in by_name:
            continue
        by_name[doc.name] = doc
        unique_docs.append(doc)

    n = len(unique_docs)
    features: Dict[str, Any] = {}
    for key, field in CHANNELS.items():
        matrix = np.zeros((n, 768), dtype=np.float32)
        mask = np.zeros(n, dtype=bool)
        for i, doc in enumerate(unique_docs):
            value = getattr(doc, field, None)
            if value is None:
                continue
            matrix[i] = np.asarray(value, dtype=np.float32).reshape(-1)
            mask[i] = True
        unit_matrix, mean, projection = _preprocess(matrix, mask)
        features[key] = {
            "matrix": unit_matrix,
            "mean": mean,
            "proj": projection,
            "mask": mask,
        }

    _RES["index"] = index
    _RES["docs"] = unique_docs
    _RES["by_name"] = by_name
    _RES["index_of"] = {doc.name: i for i, doc in enumerate(unique_docs)}
    _RES["features"] = features


def warmup() -> None:
    """预热：载入索引并算好各通道的特征（几秒级），大模型按需懒加载。"""
    with _LOCK:
        STATE.update(state="loading", message="正在载入向量索引…", error=None)
    t0 = time.time()
    try:
        with _LOCK:
            _load_index()
        with _LOCK:
            STATE.update(
                state="ready",
                message=f"已载入 {len(_RES['docs'])} 个仓库",
                loaded_at=time.time(),
                load_seconds=round(time.time() - t0, 2),
            )
    except Exception as exc:  # noqa: BLE001
        with _LOCK:
            STATE.update(state="error", message="初始化失败", error=f"{type(exc).__name__}: {exc}")
        raise


def _require_ready() -> None:
    if STATE["state"] == "error":
        raise RuntimeError(STATE["error"] or "初始化失败")
    if STATE["state"] != "ready":
        raise RuntimeError("索引尚未载入完成，请稍候")


def get_pipeline():
    """RepoSim4Py 管线（只在需要编码新仓库时加载，约 500MB）。"""
    with _LOCK:
        if _RES["pipeline"] is None:
            from transformers import pipeline

            _RES["pipeline"] = pipeline(
                model=REPOSIM4PY_MODEL_PATH,
                trust_remote_code=True,
                device_map="auto",
            )
        return _RES["pipeline"]


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def repo_payload(doc) -> Dict[str, Any]:
    """把 RepoDoc 转成前端友好的结构。"""
    available = [
        key for key, field in CHANNELS.items()
        if getattr(doc, field, None) is not None
    ]
    return {
        "name": doc.name,
        "github_url": f"https://github.com/{doc.name}",
        "stars": int(doc.stars or 0),
        "license": (doc.license or "").strip(),
        "topics": list(doc.topics or []),
        "available_layers": available,
    }


def get_repo(name: str) -> Optional[Dict[str, Any]]:
    """查询索引中是否已有该仓库。"""
    _require_ready()
    doc = _RES["by_name"].get(name)
    if doc is None:
        return None
    payload = repo_payload(doc)
    payload["indexed"] = True
    return payload


def meta_payload() -> Dict[str, Any]:
    if STATE["state"] != "ready":
        return {
            "status": STATE["state"],
            "message": STATE["message"],
            "error": STATE["error"],
            "dataset": DATASET,
        }

    docs = _RES["docs"]
    layers = []
    for key, field in CHANNELS.items():
        covered = int(_RES["features"][key]["mask"].sum())
        dim = int(_RES["features"][key]["matrix"].shape[1])
        layers.append({
            "key": key,
            "field": field,
            "dim": dim,
            "covered": covered,
            "total": len(docs),
            "ratio": round(covered / len(docs), 4),
        })

    samples = [n for n in CURATED_SAMPLES if n in _RES["by_name"]]
    if len(samples) < 6:
        for d in sorted(docs, key=lambda item: -(item.stars or 0))[:12]:
            if d.name not in samples:
                samples.append(d.name)
            if len(samples) >= 8:
                break

    return {
        "status": "ready",
        "message": STATE["message"],
        "dataset": DATASET,
        "index_size": len(docs),
        "raw_index_size": len(_RES["index"]._docs),
        "load_seconds": STATE["load_seconds"],
        "layers": layers,
        "samples": samples,
        "device": get_device(),
        "default_mode": DEFAULT_MODE,
        "domain_weights": DOMAIN_WEIGHTS,
        "drop_components": DROP_COMPONENTS,
    }


def search_domain(name: str, limit: int) -> List[Dict[str, Any]]:
    """同领域检索：四个通道各自打分后按权重融合。"""
    import numpy as np

    _require_ready()
    doc_index = _RES["index_of"].get(name)
    if doc_index is None:
        raise KeyError(name)

    docs = _RES["docs"]
    fused = np.zeros(len(docs), dtype=np.float32)
    for key in CHANNEL_KEYS:
        weight = DOMAIN_WEIGHTS.get(key, 0.0)
        if weight == 0:
            continue
        features = _RES["features"][key]
        scores = features["matrix"] @ features["matrix"][doc_index]
        scores[~features["mask"]] = 0.0
        fused += weight * scores
    fused[doc_index] = -np.inf

    order = np.argsort(-fused)
    results = []
    seen = set()
    for idx in order:
        candidate = docs[idx]
        if candidate.name == name or candidate.name in seen:
            continue
        seen.add(candidate.name)
        item = repo_payload(candidate)
        item["score"] = float(fused[idx])
        results.append(item)
        if len(results) >= limit:
            break
    return results


def search_by_embedding(name: str, layer: str, limit: int) -> List[Dict[str, Any]]:
    """按单个通道检索（预处理后的向量做余弦）。"""
    import numpy as np

    _require_ready()
    if layer not in CHANNELS:
        raise ValueError(f"未知的检索层级：{layer}")

    doc_index = _RES["index_of"].get(name)
    if doc_index is None:
        raise KeyError(name)

    features = _RES["features"][layer]
    if not features["mask"][doc_index]:
        return []

    scores = features["matrix"] @ features["matrix"][doc_index]
    scores[~features["mask"]] = 0.0
    scores[doc_index] = -np.inf
    order = np.argsort(-scores)

    docs = _RES["docs"]
    results = []
    seen = set()
    for idx in order:
        candidate = docs[idx]
        if candidate.name == name or candidate.name in seen:
            continue
        seen.add(candidate.name)
        item = repo_payload(candidate)
        item["score"] = float(scores[idx])
        results.append(item)
        if len(results) >= limit:
            break
    return results


def search(name: str, mode: str, limit: int = 10) -> List[Dict[str, Any]]:
    """统一检索入口：mode 为 domain（同领域融合）或四个通道之一。"""
    limit = max(1, min(int(limit), 100))
    resolved = resolve_mode(mode)
    if resolved == DEFAULT_MODE:
        return search_domain(name, limit)
    return search_by_embedding(name, resolved, limit)


def resolve_mode(mode: Optional[str]) -> str:
    """把外部传入的 mode 规整成内部模式名。

    旧接口里的 "repo"（已废弃的仓库整体比对）会落到同领域，避免老调用直接报错。
    """
    value = (mode or DEFAULT_MODE).strip().lower()
    if value in ("", "default", "repo"):
        return DEFAULT_MODE
    return value


# ---------------------------------------------------------------------------
# 编码新仓库（需要 GitHub token，耗时较长）
# ---------------------------------------------------------------------------

def encode_repo(name: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """用 RepoSim4Py 管线抓取仓库内容并生成多层级向量。"""
    import numpy as np

    pipeline_model = get_pipeline()

    extracted = pipeline_model.preprocess(name, github_token=github_token)
    if not extracted:
        raise ValueError("仓库不存在，或 GitHub token 无效 / 网络不可达")

    repo_info = pipeline_model.forward(extracted)[0]

    def clean(array):
        array = np.asarray(array)
        return None if np.all(array == 0) else array.reshape(-1)

    return {
        "name": repo_info.get("name") or name,
        "topics": list(repo_info.get("topics") or []),
        "stars": int(repo_info.get("stars") or 0),
        "license": (repo_info.get("license") or "").strip(),
        "embeddings": {
            "code_embedding": clean(repo_info["mean_code_embedding"]),
            "doc_embedding": clean(repo_info["mean_doc_embedding"]),
            "readme_embedding": clean(repo_info["mean_readme_embedding"]),
            "requirement_embedding": clean(repo_info["mean_requirement_embedding"]),
            "repository_embedding": clean(repo_info["mean_repo_embedding"]),
        },
    }


def persist_repo(encoded: Dict[str, Any]) -> Dict[str, Any]:
    """把编码结果写入向量索引，并用既有变换更新内存特征。"""
    import numpy as np

    _require_ready()
    from common.repo_doc import RepoDoc

    if not encoded["license"]:
        raise ValueError("该仓库缺少 License，不写入索引")
    meaningful = [
        value for key, value in encoded["embeddings"].items()
        if key in CHANNELS.values() and value is not None
    ]
    if not meaningful:
        raise ValueError("该仓库没有抽取到任何有效内容，不写入索引")

    doc = _RES["by_name"].get(encoded["name"])
    is_new = doc is None
    if is_new:
        doc = RepoDoc(
            name=encoded["name"], topics=[], stars=0, license="",
            code_embedding=None, doc_embedding=None, readme_embedding=None,
            requirement_embedding=None, repository_embedding=None,
        )
    doc.name = encoded["name"]
    doc.topics = encoded["topics"]
    doc.stars = encoded["stars"]
    doc.license = encoded["license"]
    for field, value in encoded["embeddings"].items():
        setattr(doc, field, value)

    with _LOCK:
        _RES["index"].index(doc)
        _RES["index"].persist(str(INDEX_PATH))

        docs = list(_RES["docs"])
        if is_new:
            docs.append(doc)
        _RES["docs"] = docs
        _RES["by_name"] = {d.name: d for d in docs}
        _RES["index_of"] = {d.name: i for i, d in enumerate(docs)}

        # 用既有变换给新仓库算出特征行，避免整库重算
        row = len(docs) - 1
        for key, field in CHANNELS.items():
            features = _RES["features"][key]
            value = getattr(doc, field, None)
            matrix = features["matrix"]
            if row >= matrix.shape[0]:
                matrix = np.vstack([matrix, np.zeros((1, matrix.shape[1]), dtype=np.float32)])
                features["matrix"] = matrix
                features["mask"] = np.append(features["mask"], False)
            if value is None:
                matrix[row] = 0.0
                features["mask"][row] = False
            else:
                matrix[row] = _transform_one(value, features["mean"], features["proj"])
                features["mask"][row] = True

    return {"name": doc.name}
