<script setup>
import { ref, watch } from 'vue'

import { api, parseRepoInput } from '../api'

const props = defineProps({
  open: { type: Boolean, default: false },
  initialName: { type: String, default: '' },
})

const emit = defineEmits(['close', 'done'])

const name = ref('')
const token = ref('')
const busy = ref(false)
const error = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) {
      name.value = props.initialName || ''
      error.value = ''
      busy.value = false
    }
  },
)

async function submit() {
  const repo = parseRepoInput(name.value)
  if (!repo) {
    error.value = '请输入 owner/repo 或完整的 GitHub 仓库链接'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const result = await api.indexRepo(repo, token.value.trim())
    emit('done', result)
  } catch (cause) {
    error.value = cause.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="open" class="modal-mask" @click.self="!busy && emit('close')">
    <div class="modal">
      <h3 class="modal__title">把新仓库编码进索引</h3>
      <p class="modal__desc">
        会用 RepoSim4Py 管线抓取该仓库的代码 / 文档 / README / 依赖文件，
        生成多层级向量后写入本地索引。首次调用需要加载约 500MB 的模型，
        整体可能需要几分钟。
      </p>

      <div class="field">
        <label>仓库</label>
        <input v-model="name" type="text" spellcheck="false" placeholder="owner/repo" :disabled="busy" />
      </div>

      <div class="field">
        <label>GitHub Token（可选，但强烈建议填）</label>
        <input
          v-model="token"
          type="password"
          spellcheck="false"
          placeholder="ghp_..."
          :disabled="busy"
        />
      </div>

      <div v-if="error" class="notice notice--error" style="padding: 12px 14px">
        <span class="notice__icon">⚠️</span>
        <div class="notice__text">{{ error }}</div>
      </div>

      <div v-if="busy" class="progress-note">
        <span class="spinner" />
        <span>正在抓取并编码，请勿关闭页面…</span>
      </div>

      <div class="modal__actions">
        <button class="btn" type="button" :disabled="busy" @click="emit('close')">取消</button>
        <button class="btn btn--primary" type="button" :disabled="busy" @click="submit">
          {{ busy ? '处理中…' : '开始编码' }}
        </button>
      </div>
    </div>
  </div>
</template>
