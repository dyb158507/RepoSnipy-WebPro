<script setup>
import { computed } from 'vue'

import ResultCard from './ResultCard.vue'

const LIMITS = [5, 10, 20, 30, 50]

const props = defineProps({
  results: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  limit: { type: Number, default: 10 },
  modeLabel: { type: String, default: '' },
  note: { type: String, default: '' },
})

defineEmits(['update:limit', 'retry'])

/**
 * 余弦相似度大多集中在 0.6~0.9 的窄区间，直接用绝对值画条会看不出差别，
 * 所以映射成 0.12~1 的相对比例，数值本身仍按原样展示。
 */
const barRatios = computed(() => {
  const scores = props.results.map((item) => item.score ?? 0)
  if (!scores.length) return []
  const max = Math.max(...scores)
  const min = Math.min(...scores)
  const span = max - min
  if (span <= 1e-9) return scores.map(() => 1)
  return scores.map((score) => 0.12 + 0.88 * ((score - min) / span))
})
</script>

<template>
  <div class="results-head">
    <div class="results-head__title">
      {{ modeLabel || '相似仓库' }}
      <span v-if="!loading && results.length">· {{ results.length }} 条结果</span>
    </div>
    <div class="results-head__spacer" />
    <span v-if="results.length" class="tag tag--muted">
      {{ note || '得分条按本次结果相对归一化' }}
    </span>
    <label class="select">
      显示
      <select :value="limit" @change="$emit('update:limit', Number($event.target.value))">
        <option v-for="option in LIMITS" :key="option" :value="option">{{ option }}</option>
      </select>
      条
    </label>
  </div>

  <div v-if="loading" class="result-list">
    <div v-for="index in 5" :key="index" class="skeleton">
      <div class="sk sk--rank" />
      <div>
        <div class="sk sk--line" style="width: 42%" />
        <div class="sk sk--line" style="width: 72%; margin-bottom: 0" />
      </div>
    </div>
  </div>

  <div v-else-if="error" class="notice notice--error">
    <span class="notice__icon">⚠️</span>
    <div>
      <div class="notice__title">检索失败</div>
      <div class="notice__text">{{ error }}</div>
      <button class="btn btn--sm" style="margin-top: 12px" type="button" @click="$emit('retry')">
        重试
      </button>
    </div>
  </div>

  <div v-else-if="!results.length" class="empty">
    该维度下没有可比较的仓库，换一个检索维度试试。
  </div>

  <div v-else class="result-list">
    <ResultCard
      v-for="(item, index) in results"
      :key="item.name"
      :item="item"
      :rank="index + 1"
      :ratio="barRatios[index] ?? 1"
      :display-score="(item.score ?? 0).toFixed(4)"
    />
  </div>
</template>
