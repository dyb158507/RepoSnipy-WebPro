<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { api, formatNumber, parseRepoInput } from './api'
import AppHeader from './components/AppHeader.vue'
import HeroSearch from './components/HeroSearch.vue'
import IndexDialog from './components/IndexDialog.vue'
import ModeTabs from './components/ModeTabs.vue'
import RepoSummary from './components/RepoSummary.vue'
import ResultList from './components/ResultList.vue'

const THEME_KEY = 'reposnipy.theme'

const MODE_LABELS = {
  domain: '同领域相似',
  code: '代码相似',
  doc: '文档字符串相似',
  readme: 'README 相似',
  requirement: '依赖文件相似',
}

const MODE_NOTES = {
  domain: '得分 = readme 0.45 / doc 0.35 / code 0.20 加权融合，得分条按本次结果相对归一化',
  code: '得分 = 代码通道余弦（已归一化并去掉前 8 个主方向）',
  doc: '得分 = 文档字符串通道余弦（已归一化并去掉前 8 个主方向）',
  readme: '得分 = README 通道余弦（已归一化并去掉前 8 个主方向）',
  requirement: '得分 = 依赖文件通道余弦（已归一化并去掉前 8 个主方向）',
}

/* ------------------------------- 状态 ---------------------------------- */

const theme = ref('dark')
const meta = ref(null)
const metaState = ref('loading')
const metaError = ref('')

const input = ref('')
const query = ref(null)
const queryError = ref('')
const queryErrorKind = ref('')

const mode = ref('domain')
const limit = ref(10)
const results = ref([])
const resultsLoading = ref(false)
const resultsError = ref('')
const searchBusy = ref(false)

const showIndexDialog = ref(false)

let pollTimer = null
let heartbeatTimer = null
let searchSeq = 0
// 后端是否掉过线。用它而不是 metaState 判断恢复，
// 因为后端重启时 /api/meta 会先返回 loading 再返回 ready。
let backendDown = false

// 空闲时每隔几秒静默探一次后端，掉线了才提示，避免界面一直假装"就绪"
const HEARTBEAT_MS = 6000

/* ------------------------------- 主题 ---------------------------------- */

function applyTheme(value) {
  document.documentElement.dataset.theme = value
  try {
    localStorage.setItem(THEME_KEY, value)
  } catch {
    /* 隐私模式下写入失败可以忽略 */
  }
}

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

watch(theme, applyTheme)

/* ---------------------------- 初始化 / 元信息 --------------------------- */

async function loadMeta() {
  try {
    const data = await api.meta()
    meta.value = data
    if (data.status === 'ready') {
      metaState.value = 'ready'
      metaError.value = ''
      // 后端刚恢复：把之前失败的结果自动补回来
      if (backendDown) {
        backendDown = false
        if (query.value) loadResults()
      }
      scheduleHeartbeat()
    } else if (data.status === 'error') {
      metaState.value = 'error'
      metaError.value = data.error || data.message
    } else {
      metaState.value = 'loading'
      schedulePoll()
    }
  } catch (cause) {
    metaState.value = 'error'
    metaError.value = cause.message
    schedulePoll()
  }
}

function schedulePoll() {
  if (pollTimer) return
  pollTimer = setTimeout(() => {
    pollTimer = null
    loadMeta()
  }, 1500)
}

function scheduleHeartbeat() {
  if (heartbeatTimer) return
  heartbeatTimer = setTimeout(() => {
    heartbeatTimer = null
    loadMeta().then(() => {
      if (metaState.value === 'ready') scheduleHeartbeat()
    })
  }, HEARTBEAT_MS)
}

/* ------------------------------- 检索 ---------------------------------- */

/** 后端掉线时统一处理：顶部状态切成断开，并持续重连。 */
function noteBackendProblem(cause) {
  if (!cause?.offline) return
  backendDown = true
  metaState.value = 'error'
  metaError.value = cause.message
  schedulePoll()
}

function modeAvailable(repo, key) {
  if (!repo) return false
  const layers = repo.available_layers || []
  if (key === 'domain') return layers.length > 0
  return layers.includes(key)
}

async function loadResults() {
  if (!query.value) return
  const seq = ++searchSeq
  resultsLoading.value = true
  resultsError.value = ''
  try {
    const data = await api.search(query.value.name, mode.value, limit.value)
    if (seq !== searchSeq) return // 已经有更新的请求了，丢弃这次结果
    backendDown = false
    results.value = data.results || []
  } catch (cause) {
    if (seq !== searchSeq) return
    results.value = []
    resultsError.value = cause.message
    noteBackendProblem(cause)
  } finally {
    if (seq === searchSeq) resultsLoading.value = false
  }
}

async function runSearch(rawName) {
  const name = parseRepoInput(rawName ?? input.value)
  queryError.value = ''
  queryErrorKind.value = ''

  if (!name) {
    query.value = null
    results.value = []
    queryErrorKind.value = 'invalid'
    queryError.value = '请输入 owner/repo 形式，或直接粘贴 GitHub 仓库链接'
    return
  }

  input.value = name
  searchBusy.value = true
  try {
    const repo = await api.repo(name)
    query.value = repo
    if (!modeAvailable(repo, mode.value)) {
      mode.value = (repo.available_layers || [])[0] ?? 'domain'
    }
    await loadResults()
    syncHash()
  } catch (cause) {
    query.value = null
    results.value = []
    noteBackendProblem(cause)
    if (cause.status === 404) {
      queryErrorKind.value = 'not-indexed'
      queryError.value = cause.message
    } else {
      queryErrorKind.value = 'failed'
      queryError.value = cause.message
    }
  } finally {
    searchBusy.value = false
  }
}

function retryAll() {
  loadMeta()
  if (query.value) loadResults()
}

watch(mode, () => {
  if (query.value) {
    loadResults()
    syncHash()
  }
})

watch(limit, () => {
  if (query.value) loadResults()
})

/* ----------------------------- URL 同步 -------------------------------- */

function syncHash() {
  const params = new URLSearchParams()
  if (query.value) {
    params.set('repo', query.value.name)
    params.set('mode', mode.value)
  }
  const next = params.toString()
  history.replaceState(null, '', next ? `#${next}` : '#')
}

function restoreFromHash() {
  const params = new URLSearchParams(location.hash.replace(/^#/, ''))
  const repo = params.get('repo')
  // 旧链接里的 mode=repo（已废弃的仓库整体比对）统一落到同领域
  const savedMode = params.get('mode') === 'repo' ? 'domain' : params.get('mode')
  if (savedMode && MODE_LABELS[savedMode]) mode.value = savedMode
  if (repo) {
    input.value = repo
    return true
  }
  return false
}

/* ------------------------------- 其他 ---------------------------------- */

async function onIndexed() {
  showIndexDialog.value = false
  await loadMeta()
  if (input.value) await runSearch(input.value)
}

const modeLabel = computed(() => MODE_LABELS[mode.value] ?? '相似仓库')
const modeNote = computed(() => MODE_NOTES[mode.value] ?? '')
const notReady = computed(() => metaState.value !== 'ready')

onMounted(() => {
  let stored = 'dark'
  try {
    stored = localStorage.getItem(THEME_KEY) || 'dark'
  } catch {
    stored = 'dark'
  }
  theme.value = stored
  applyTheme(stored)

  loadMeta()

  if (restoreFromHash()) {
    runSearch(input.value)
  }
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
  if (heartbeatTimer) clearTimeout(heartbeatTimer)
})
</script>

<template>
  <AppHeader :state="metaState" :meta="meta" :theme="theme" @toggle-theme="toggleTheme" />

  <main class="main page">
    <HeroSearch
      v-model="input"
      :meta="meta"
      :compact="Boolean(query)"
      :busy="searchBusy"
      :disabled="notReady"
      @search="runSearch()"
      @pick="runSearch($event)"
    />

    <div v-if="metaState === 'error'" class="notice notice--error">
      <span class="notice__icon">🔌</span>
      <div>
        <div class="notice__title">后端服务已断开</div>
        <div class="notice__text">{{ metaError }}</div>
        <div class="notice__text" style="margin-top: 6px">
          页面每 1.5 秒会自动重连一次；如果你重启了后端，也可以直接点下面的按钮。
        </div>
        <button class="btn btn--sm" style="margin-top: 12px" type="button" @click="retryAll">
          立即重试
        </button>
      </div>
    </div>

    <div v-else-if="metaState === 'loading'" class="notice">
      <span class="notice__icon"><span class="spinner" /></span>
      <div>
        <div class="notice__title">正在载入向量索引</div>
        <div class="notice__text">首次启动会读取索引文件与聚类表，通常只需要几秒钟。</div>
      </div>
    </div>

    <template v-if="query">
      <section class="section">
        <h2 class="section__title">查询仓库</h2>
        <RepoSummary :repo="query" />
      </section>

      <section class="section">
        <h2 class="section__title">检索模式</h2>
        <ModeTabs
          :active="mode"
          :repo="query"
          :weights="meta?.domain_weights"
          @change="mode = $event"
        />
      </section>

      <section class="section">
        <ResultList
          :results="results"
          :loading="resultsLoading"
          :error="resultsError"
          :limit="limit"
          :mode-label="modeLabel"
          :note="modeNote"
          @update:limit="limit = $event"
          @retry="loadResults"
        />
      </section>
    </template>

    <div v-else-if="queryErrorKind === 'not-indexed'" class="notice notice--warn">
      <span class="notice__icon">📦</span>
      <div>
        <div class="notice__title">这个仓库还没有被索引</div>
        <div class="notice__text">{{ queryError }}</div>
        <button
          class="btn btn--sm btn--primary"
          style="margin-top: 12px"
          type="button"
          @click="showIndexDialog = true"
        >
          编码并加入索引
        </button>
      </div>
    </div>

    <div v-else-if="queryError" class="notice notice--error">
      <span class="notice__icon">⚠️</span>
      <div>
        <div class="notice__title">检索失败</div>
        <div class="notice__text">{{ queryError }}</div>
      </div>
    </div>
  </main>

  <footer class="footer">
    <div class="page footer__inner">
      <span v-if="meta?.status === 'ready'">
        数据集 <b class="mono">{{ meta.dataset }}</b> · 索引
        <b class="mono">{{ formatNumber(meta.index_size) }}</b> 个仓库 · 计算设备
        <b class="mono">{{ meta.device }}</b> · 载入 {{ meta.load_seconds }}s
      </span>
      <span class="footer__spacer" />
      <a href="https://github.com/RepoMining/RepoSim4Py" target="_blank" rel="noreferrer">RepoSim4Py</a>
      <a href="https://github.com/RepoMining/RepoSnipy" target="_blank" rel="noreferrer">RepoSnipy</a>
      <a href="/docs" target="_blank" rel="noreferrer">API</a>
    </div>
  </footer>

  <IndexDialog
    :open="showIndexDialog"
    :initial-name="input"
    @close="showIndexDialog = false"
    @done="onIndexed"
  />
</template>
