<script setup>
import { computed } from 'vue'

const props = defineProps({
  active: { type: String, required: true },
  repo: { type: Object, default: null },
  weights: { type: Object, default: null },
})

defineEmits(['change'])

const CHANNEL_MODES = [
  { key: 'code', label: '代码', hint: '函数体代码向量，单通道检索' },
  { key: 'doc', label: '文档字符串', hint: 'docstring 向量，单通道检索' },
  { key: 'readme', label: 'README', hint: 'README 文本向量，单通道检索' },
  { key: 'requirement', label: '依赖文件', hint: 'requirements / setup.py 向量，单通道检索' },
]

const layers = computed(() => new Set(props.repo?.available_layers || []))

const domainHint = computed(() => {
  const w = props.weights
  const text = w
    ? `readme ${w.readme} / doc ${w.doc} / code ${w.code} / requirement ${w.requirement}`
    : 'readme / doc / code 加权融合'
  return `同领域检索：四个通道各自打分后加权融合（${text}）`
})

function disabled(mode) {
  if (!props.repo) return true
  if (mode.key === 'domain') return layers.value.size === 0
  return !layers.value.has(mode.key)
}
</script>

<template>
  <div class="modes">
    <span class="modes__group-label">默认</span>
    <button
      class="mode-tab mode-tab--domain"
      :class="{ 'mode-tab--active': active === 'domain' }"
      type="button"
      :title="domainHint"
      :disabled="disabled({ key: 'domain' })"
      @click="$emit('change', 'domain')"
    >
      <i class="mode-tab__dot" />
      同领域
    </button>

    <span class="modes__divider" />

    <span class="modes__group-label">单通道</span>
    <button
      v-for="mode in CHANNEL_MODES"
      :key="mode.key"
      class="mode-tab"
      :class="{ 'mode-tab--active': active === mode.key }"
      type="button"
      :title="mode.hint"
      :disabled="disabled(mode)"
      @click="$emit('change', mode.key)"
    >
      <i class="mode-tab__dot" />
      {{ mode.label }}
    </button>
  </div>
</template>
