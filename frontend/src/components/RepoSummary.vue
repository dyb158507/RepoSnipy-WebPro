<script setup>
import { computed } from 'vue'

import { formatStars } from '../api'

const props = defineProps({
  repo: { type: Object, required: true },
})

const LAYERS = [
  { key: 'code', label: '代码' },
  { key: 'doc', label: '文档字符串' },
  { key: 'readme', label: 'README' },
  { key: 'requirement', label: '依赖文件' },
]

const available = computed(() => new Set(props.repo.available_layers || []))

const visibleTopics = computed(() => (props.repo.topics || []).slice(0, 12))
const hiddenTopicCount = computed(() => Math.max(0, (props.repo.topics?.length || 0) - 12))
</script>

<template>
  <div class="card query-card">
    <div class="query-card__main">
      <div class="query-card__repo">
        <a :href="repo.github_url" target="_blank" rel="noreferrer">{{ repo.name }}</a>
        <a :href="repo.github_url" target="_blank" rel="noreferrer" title="在 GitHub 打开">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round">
            <path d="M14 4h6v6" />
            <path d="M20 4 11 13" />
            <path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
          </svg>
        </a>
      </div>

      <div class="query-card__meta">
        <span>
          <b>{{ formatStars(repo.stars) }}</b> stars
        </span>
        <span v-if="repo.license">
          License <b>{{ repo.license }}</b>
        </span>
        <span v-else class="tag tag--muted">无 License</span>
        <span>
          <b>{{ repo.topics?.length || 0 }}</b> 个 topics
        </span>
      </div>

      <div v-if="visibleTopics.length" class="query-card__topics">
        <span v-for="topic in visibleTopics" :key="topic" class="tag tag--topic">{{ topic }}</span>
        <span v-if="hiddenTopicCount" class="tag tag--muted">+{{ hiddenTopicCount }}</span>
      </div>
    </div>

    <div class="query-card__side">
      <div class="side-title">检索通道可用性</div>
      <div class="layers">
        <div v-for="layer in LAYERS" :key="layer.key" class="layer-row">
          <span>{{ layer.label }}</span>
          <span class="layer-row__bar">
            <span
              class="layer-row__fill"
              :class="{ 'layer-row__fill--off': !available.has(layer.key) }"
              :style="{ width: available.has(layer.key) ? '100%' : '14%' }"
            />
          </span>
          <span class="layer-row__value">
            {{ available.has(layer.key) ? '可用' : '缺失' }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
