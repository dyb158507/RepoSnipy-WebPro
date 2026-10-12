<script setup>
import { computed } from 'vue'

import { formatNumber } from '../api'

const props = defineProps({
  modelValue: { type: String, default: '' },
  meta: { type: Object, default: null },
  busy: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'search', 'pick'])

// 每个通道的向量维度（四个通道都是 768）
const channelDim = computed(
  () => props.meta?.layers?.[0]?.dim ?? 768,
)

function onInput(event) {
  emit('update:modelValue', event.target.value)
}

function submit() {
  emit('search')
}
</script>

<template>
  <section class="hero" :class="{ 'hero--compact': compact }">
    <template v-if="!compact">
      <div class="hero__badge">
        <span>⚡</span>
        <span>
          RepoSim4Py 驱动的
          <b>多层级语义检索</b>
        </span>
      </div>
      <h1 class="hero__title">
        找到语义上<em>最相似</em>的 Python 仓库
      </h1>
      <p class="hero__sub">
        输入一个 GitHub 仓库，从代码、文档字符串、README、依赖文件四个维度，
        找出语义上同领域的其他仓库。
      </p>
    </template>

    <div class="search">
      <div class="search__box">
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.2-3.2" />
        </svg>
        <input
          class="search__input"
          type="text"
          spellcheck="false"
          autocomplete="off"
          placeholder="owner/repo，或粘贴 GitHub 链接，例如 numpy/numpy"
          :value="modelValue"
          :disabled="disabled"
          @input="onInput"
          @keyup.enter="submit"
        />
        <button class="btn btn--primary" type="button" :disabled="busy || disabled" @click="submit">
          <span v-if="busy" class="spinner" />
          <span>{{ busy ? '检索中' : '检索' }}</span>
        </button>
      </div>

      <div v-if="meta?.samples?.length" class="search__hint">
        <span>试试：</span>
        <button
          v-for="sample in meta.samples.slice(0, 6)"
          :key="sample"
          class="chip-btn"
          type="button"
          @click="emit('pick', sample)"
        >
          {{ sample }}
        </button>
      </div>
    </div>

    <div v-if="!compact && meta?.status === 'ready'" class="stats">
      <div class="stat">
        <div class="stat__value">{{ formatNumber(meta.index_size) }}</div>
        <div class="stat__label">已索引仓库</div>
      </div>
      <div class="stat">
        <div class="stat__value">{{ meta.layers?.length ?? 5 }}</div>
        <div class="stat__label">检索通道</div>
      </div>
      <div class="stat">
        <div class="stat__value">{{ channelDim }}</div>
        <div class="stat__label">单通道维度</div>
      </div>
      <div class="stat">
        <div class="stat__value">{{ (meta.device || 'cpu').toUpperCase() }}</div>
        <div class="stat__label">计算设备</div>
      </div>
    </div>
  </section>
</template>
