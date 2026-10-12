# RepoSnipy · 语义化 Python 仓库检索

输入一个 GitHub 上的 Python 仓库，从**代码、文档字符串、README、依赖文件**四个通道
找出语义上同领域的其他仓库（默认按权重融合排序，也可以只看单个通道）。

Vue 3 前端 + FastAPI 后端。模型、索引、虚拟环境全部放在项目内，
**整个文件夹可以直接拷走运行，不需要联网、不需要额外安装**。

## 快速开始

双击 `run_api.bat`。它会启动后端、等索引载入完成、然后自动打开浏览器。

```
界面地址 : http://localhost:8000/
接口文档 : http://localhost:8000/docs
```

控制台窗口不要关，关掉就等于停止服务。

### 另一种启动方式（改前端代码时用）

双击 `run_web.bat`：后端跑在 8000，Vite 开发服务器跑在 5173，前端改动会热更新。
改完后在 `frontend` 目录执行一次 `npm run build`，之后 `run_api.bat` 就能用上新界面。

## 工作原理

1. 用 [RepoSim4Py](https://github.com/RepoMining/RepoSim4Py) 管线抓取仓库内容，
   分别对函数体代码、docstring、README、依赖文件编码出 768 维向量。
2. 把这些向量连同仓库元信息存进 [DocArray](https://github.com/docarray/docarray)
   的内存索引（`data/index_developing.bin`，约 9600 个热门 Python 仓库）。
3. 检索前对每个通道做一次预处理：**减去全库均值 → 去掉方差最大的前 8 个主方向 →
   逐行归一化**。这一步是为了消除 mean-pooled 向量严重的"各向异性"——不加处理时，
   两个毫不相干的仓库 README 余弦也有 0.49，真正的信号被公共偏置盖住了。
4. 检索时四个通道各自打分，再按权重融合：

   | 通道 | 权重 | 理由 |
   | --- | --- | --- |
   | README | 0.45 | "同领域"主要由 README 的描述决定 |
   | docstring | 0.35 | docstring 描述这个库提供什么功能 |
   | 代码 | 0.20 | 单通道效果最好，但保留较小权重以免纯文本偏好主导 |
   | 依赖文件 | 0.00 | 单通道效果最差（接近随机）且只有 56% 覆盖率 |

   权重可以用环境变量覆盖：`set REPOSNIPY_DOMAIN_WEIGHTS=0.3,0.25,0.45,0`。

界面上默认的「同领域」就是这条融合链路；「单通道」分组下的四个标签页用于按单一维度细看。
注意：原先的"仓库整体"（四段拼接成 3072 维再算余弦）已经移除——那个做法会让各通道的
实际权重由向量范数决定，而不是由设计决定。

如果输入的仓库不在索引里，可以在界面上点「编码并加入索引」，
填 GitHub Token 实时抓取并编码，然后写回本地索引。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `serve.py` | 启动器：设置离线环境变量、启动后端、就绪后打开浏览器 |
| `api/engine.py` | 检索引擎：索引与模型的加载、检索、编码、写回 |
| `api/main.py` | FastAPI 路由 + 静态资源托管 |
| `api/schemas.py` | 接口的请求 / 响应模型 |
| `common/repo_doc.py` | 索引里的数据结构 `RepoDoc` |
| `data/` | 向量索引（`index_developing.bin` 开发版 / `index.bin` 产品版） |
| `models/RepoSim4Py` | 本地模型，供编码新仓库使用 |
| `frontend/` | Vue 3 + Vite 前端，详见 `frontend/README.md` |
| `Python310/` `.venv/` | 便携式 Python 运行时与虚拟环境 |

目录里代码用的都是相对路径，移动或重命名文件夹不影响它们。

### 换电脑 / 换目录怎么办

虚拟环境里有两处会写死绝对路径（`.venv\pyvenv.cfg` 的 `home`，以及
`.venv\Scripts\python.exe` 这个内嵌了基础解释器路径的启动器），换位置后会失效。

`run_api.bat` / `run_web.bat` 在启动前会自动运行 `bootstrap.py` 做自检和修复：
它由项目自带的基础解释器执行（不依赖虚拟环境），发现路径不对就改回来，
发现启动器失效就按当前路径重新生成，然后实际启动一次验证。

所以**整个文件夹直接拷到另一台电脑（同样是 64 位 Windows）就能跑**，
第一次启动会多花几秒钟做修复。也可以手动运行：

```cmd
Python310\cpython-3.10-windows-x86_64-none\python.exe bootstrap.py
```

## 环境说明

- Python 3.10（`Python310/` + `.venv/`，依赖已装好）

## 从 GitHub 克隆后如何运行

仓库里**只有源码**。模型和向量索引因为体积太大（合计约 700 MB）没有入库，
需要从 [Releases](../../releases) 页面下载，然后按下面的结构放好：

```
RepoSnipy-Web/
├── data/
│   └── index_developing.bin     ← 从 Releases 下载（向量索引，约 216 MB）
├── models/
│   └── RepoSim4Py/              ← 从 Releases 下载压缩包后解压（约 484 MB）
├── api/  common/  frontend/     ← 仓库里已有
└── serve.py  bootstrap.py  run_api.bat
```

然后准备运行环境（需要联网，约 10 分钟）：

```cmd
:: 1. 建虚拟环境并装依赖（用 Python 3.10）
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

:: 2. 构建前端（需要 Node.js 18 以上）
cd frontend
npm install
npm run build
cd ..

:: 3. 启动
run_api.bat
```

> 如果你拿到的是**别人打包好的完整文件夹**（里面含 `Python310/` 和 `.venv/`），
> 上面第 1、2 步都不用做，直接双击 `run_api.bat` 即可——启动脚本会自动修复
> 虚拟环境里因为换机器而失效的绝对路径。
- 只有在需要重建环境时才用 `requirements.txt`（那个步骤需要联网）
- 数据集可切换：设置环境变量 `REPOSNIPY_DATASET=product` 会改用 `data/index.bin`
- 端口可切换：设置 `REPOSNIPY_PORT=8010`

## 常见问题

**.bat 双击后一堆「不是内部或外部命令」**

批处理文件必须用 CRLF 换行保存。用 LF（Unix 换行）保存会让 cmd 拆错行，
环境变量也不会生效。改动 `.bat` 后确认一下换行格式。

**页面显示「后端服务已断开」**

说明后端窗口被关掉了。重新双击 `run_api.bat`，页面会自己重连，不用刷新。

**检索时提示仓库未收录**

索引里是约 9600 个 2024 年 3 月前的热门 Python 仓库。
新仓库可以用「编码并加入索引」实时补齐（需要 GitHub Token）。

## 数据来源与致谢

索引与模型来自 [RepoMining/RepoSnipy](https://github.com/RepoMining/RepoSnipy)、
[RepoSim4Py](https://github.com/RepoMining/RepoSim4Py)，
向量模型底座为 UniXCoder / AdvTest。遵循原始项目的 MIT 协议。
