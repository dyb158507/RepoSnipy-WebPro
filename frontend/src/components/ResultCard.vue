<script setup>
import { computed } from 'vue'

import { formatStars } from '../api'

const props = defineProps({
  item: { type: Object, required: true },
  rank: { type: Number, default: 1 },
  ratio: { type: Number, default: 1 },
  displayScore: { type: String, default: '' },
})

const rankClass = computed(() => (props.rank <= 3 ? ` result__rank--${props.rank}` : ''))
const topics = computed(() => (props.item.topics || []).slice(0, 6))
const hiddenTopics = computed(() => Math.max(0, (props.item.topics?.length || 0) - 6))
</script>

<template>
  <article class="result" :style="{ animationDelay: `${Math.min(rank, 12) * 26}ms` }">
    <div class="result__rank" :class="rankClass">{{ rank }}</div>

    <div class="result__body">
      <div class="result__top">
        <span class="result__name">
          <a :href="item.github_url" target="_blank" rel="noreferrer">{{ item.name }}</a>
        </span>

        <span class="result__stars">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" opacity=".75">
            <path d="m12 3.6 2.6 5.4 5.9.8-4.3 4.1 1.1 5.9L12 17l-5.3 2.8 1.1-5.9L3.5 9.8l5.9-.8z" />
          </svg>
          {{ formatStars(item.stars) }}
        </span>

        <div class="result__score">
          <span class="result__score-value">{{ displayScore }}</span>
          <span class="result__score-bar">
            <span class="result__score-fill" :style="{ width: `${Math.max(ratio * 100, 4)}%` }" />
          </span>
        </div>
      </div>

      <div class="result__chips">
        <span v-if="item.license" class="tag tag--license">{{ item.license }}</span>
        <span v-for="topic in topics" :key="topic" class="tag">{{ topic }}</span>
        <span v-if="hiddenTopics" class="tag tag--muted">+{{ hiddenTopics }}</span>
      </div>
    </div>
  </article>
</template>
