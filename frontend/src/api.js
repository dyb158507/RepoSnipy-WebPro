/**
 * 后端接口封装。
 * 开发模式下由 Vite 代理 /api 到 http://127.0.0.1:8000（见 vite.config.js）。
 */

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function request(path, options) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, options)
  } catch (cause) {
    const error = new Error('连不上后端服务。请确认后端窗口还在运行（默认 http://localhost:8000）。')
    error.offline = true
    error.cause = cause
    throw error
  }

  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    const detail = data?.detail
    const error = new Error(typeof detail === 'string' ? detail : `请求失败（HTTP ${response.status}）`)
    error.status = response.status
    // 503 一般是索引还没载入完，或后端正在重启
    if (response.status === 503) error.offline = true
    throw error
  }
  return data
}

export const api = {
  meta: () => request('/api/meta'),

  repo: (name) => request(`/api/repo?name=${encodeURIComponent(name)}`),

  search: (name, mode, limit) =>
    request(
      `/api/search?name=${encodeURIComponent(name)}&mode=${encodeURIComponent(mode)}&limit=${limit}`,
    ),

  indexRepo: (name, githubToken) =>
    request('/api/index', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, github_token: githubToken || null }),
    }),
}

const REPO_PATTERN =
  /^((git@|http(s)?:\/\/)?(github\.com)(\/|:))?(?<owner>[\w.-]+)\/(?<repo>[\w.-]+?)(\.git)?\/?$/

/** 把用户输入（URL / owner/repo / git@ 写法）统一成 owner/repo。 */
export function parseRepoInput(raw) {
  const text = (raw ?? '').trim()
  if (!text) return null
  const match = REPO_PATTERN.exec(text)
  if (!match?.groups) return null
  return `${match.groups.owner}/${match.groups.repo}`
}

/** 12345 -> 12.3k */
export function formatStars(value) {
  const num = Number(value) || 0
  if (num >= 1000) {
    return `${(num / 1000).toFixed(num >= 10000 ? 0 : 1)}k`
  }
  return String(num)
}

export function formatNumber(value) {
  const num = Number(value) || 0
  return num.toLocaleString('zh-CN')
}
