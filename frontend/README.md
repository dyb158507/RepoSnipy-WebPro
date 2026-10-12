# RepoSnipy 前端（Vue 3 + Vite）

通过 HTTP 接口调用 `../api` 里的 FastAPI 后端，提供检索界面。

## 开发模式

需要同时跑后端和前端两个进程（也可以直接双击项目根目录的 `run_web.bat`）：

```bash
# 终端 1：后端（项目根目录）
.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000

# 终端 2：前端（frontend 目录）
npm run dev     # http://localhost:5173
```

开发服务器会把 `/api/*` 反向代理到 `http://127.0.0.1:8000`（见 `vite.config.js`），
所以前端代码里直接写 `/api/...` 即可，不需要处理跨域。
后端端口不是 8000 时，用环境变量 `VITE_API_TARGET` 指定。

依赖已经随项目一起打包在 `node_modules` 里，不需要联网安装。

## 生产 / 演示模式

```bash
npm run build   # 产物输出到 dist/
```

`dist/index.html` 存在时，FastAPI 会直接把 `dist/` 挂到根路径，
于是只跑后端（`run_api.bat`）就能访问完整界面，适合答辩演示。
改完前端源码后需要重新执行 `npm run build`。

## 目录

```
src/
  api.js                  接口封装、输入解析（URL -> owner/repo）、数字格式化
  App.vue                 页面状态与流程编排
  styles/main.css         设计系统（配色、卡片、按钮、暗/亮主题）
  components/
    AppHeader.vue         顶栏：品牌、索引状态、主题切换
    HeroSearch.vue        搜索区：输入框、示例仓库、统计数字
    RepoSummary.vue       查询仓库卡片：元信息、各检索层级可用性
    ModeTabs.vue          5 个向量层级切换
    ResultList.vue        结果列表：骨架屏、相对得分、条数选择
    ResultCard.vue        单条结果
    IndexDialog.vue       把新仓库编码入库的弹窗
```

## 交互

- 输入框回车即检索，支持 `numpy/numpy`、`https://github.com/numpy/numpy` 等写法
- 地址栏带 `#repo=...&mode=...`，可直接分享某次检索结果
- 右上角可切换深浅主题，选择会记在 localStorage
- 后端断开时状态栏会提示并自动重连
