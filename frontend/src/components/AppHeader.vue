<script setup>
import { computed } from 'vue'

import { formatNumber } from '../api'

const props = defineProps({
  state: { type: String, default: 'loading' },
  meta: { type: Object, default: null },
  theme: { type: String, default: 'dark' },
})

defineEmits(['toggle-theme'])

const statusClass = computed(() => {
  if (props.state === 'ready') return 'status-pill'
  if (props.state === 'error') return 'status-pill status-pill--error'
  return 'status-pill status-pill--loading'
})

const statusText = computed(() => {
  if (props.state === 'ready') {
    return `索引就绪 · ${formatNumber(props.meta?.index_size)} 个仓库`
  }
  if (props.state === 'error') return '后端已断开 · 正在重连'
  return '正在载入索引…'
})
</script>

<template>
  <header class="topbar">
    <div class="page topbar__inner">
      <a class="brand" href="#/">
        <span class="brand__mark">🐉</span>
        <span class="brand__text">
          <strong>RepoSnipy</strong>
          <span>Neural Repo Search</span>
        </span>
      </a>

      <div class="topbar__spacer" />

      <div class="topbar__actions">
        <span :class="statusClass" :title="meta?.message || ''">
          <i class="status-pill__dot" />
          {{ statusText }}
        </span>

        <a class="icon-btn" href="/docs" target="_blank" rel="noreferrer" title="接口文档">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H10v16H5.5A1.5 1.5 0 0 1 4 18.5v-13Z" />
            <path d="M14 4h4.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H14" />
            <path d="M10 4h4v16h-4z" opacity=".45" />
          </svg>
        </a>

        <button
          class="icon-btn"
          type="button"
          :title="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          @click="$emit('toggle-theme')"
        >
          <svg v-if="theme === 'dark'" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <circle cx="12" cy="12" r="4.2" />
            <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
          </svg>
          <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
          </svg>
        </button>
      </div>
    </div>
  </header>
</template>
