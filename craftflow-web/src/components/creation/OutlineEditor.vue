<script setup lang="ts">
import { ref, computed } from 'vue'

/** 大纲条目 */
export interface OutlineItem {
  title: string
  summary: string
}

const props = defineProps<{
  /** 大纲列表 */
  items: OutlineItem[]
  /** 是否正在提交 */
  loading?: boolean
}>()

const emit = defineEmits<{
  /** 确认大纲（不修改） */
  confirm: []
  /** 更新大纲（携带修改后的数据） */
  update: [items: OutlineItem[]]
}>()

/** 内部编辑副本 */
const editableItems = ref<OutlineItem[]>(
  props.items.map((item) => ({ ...item })),
)

/** 当前编辑中的条目索引（-1 表示无） */
const editingIndex = ref(-1)

/** 编辑缓冲区 */
const editBuffer = ref<OutlineItem>({ title: '', summary: '' })

const hasChanges = computed(() => {
  if (editableItems.value.length !== props.items.length) return true
  return editableItems.value.some(
    (item, i) =>
      item.title !== props.items[i]?.title ||
      item.summary !== props.items[i]?.summary,
  )
})

function startEdit(index: number): void {
  editingIndex.value = index
  editBuffer.value = { ...editableItems.value[index]! }
}

function cancelEdit(): void {
  editingIndex.value = -1
}

function saveEdit(): void {
  const idx = editingIndex.value
  if (idx < 0) return
  editableItems.value[idx] = { ...editBuffer.value }
  editingIndex.value = -1
}

function deleteItem(index: number): void {
  editableItems.value.splice(index, 1)
  // 如果正在编辑的条目被删除或在其前面，重置编辑状态
  if (editingIndex.value === index) {
    editingIndex.value = -1
  } else if (editingIndex.value > index) {
    editingIndex.value--
  }
}

function onConfirm(): void {
  emit('confirm')
}

function onUpdate(): void {
  emit('update', editableItems.value.map((item) => ({ ...item })))
}
</script>

<template>
  <div class="outline-editor">
    <div class="outline-header">
      <h3 class="outline-title">文章大纲</h3>
      <p class="outline-hint">点击条目可编辑标题和摘要</p>
    </div>

    <ol class="outline-list">
      <li
        v-for="(item, index) in editableItems"
        :key="index"
        class="outline-item"
      >
        <!-- 查看模式 -->
        <div
          v-if="editingIndex !== index"
          class="item-view"
          @click="startEdit(index)"
        >
          <span class="item-number">{{ index + 1 }}</span>
          <div class="item-content">
            <p class="item-title">{{ item.title }}</p>
            <p class="item-summary">{{ item.summary }}</p>
          </div>
          <div class="item-actions">
            <span class="edit-icon" title="编辑">&#9998;</span>
            <button
              class="btn-icon btn-delete"
              title="删除"
              @click.stop="deleteItem(index)"
            >
              &#10005;
            </button>
          </div>
        </div>

        <!-- 编辑模式 -->
        <div v-else class="item-edit">
          <span class="item-number">{{ index + 1 }}</span>
          <div class="edit-fields">
            <input
              v-model="editBuffer.title"
              class="edit-input"
              placeholder="章节标题"
              maxlength="200"
            />
            <textarea
              v-model="editBuffer.summary"
              class="edit-textarea"
              placeholder="章节摘要"
              :rows="2"
              maxlength="1000"
            />
          </div>
          <div class="edit-actions">
            <button class="btn-icon btn-save" title="保存" @click="saveEdit">
              &#10003;
            </button>
            <button class="btn-icon btn-cancel" title="取消" @click="cancelEdit">
              &#10005;
            </button>
          </div>
        </div>
      </li>
    </ol>

    <div class="outline-footer">
      <button
        class="btn btn-primary"
        :disabled="loading"
        @click="onConfirm"
      >
        确认大纲
      </button>
      <button
        v-if="hasChanges"
        class="btn btn-secondary"
        :disabled="loading"
        @click="onUpdate"
      >
        更新大纲
      </button>
    </div>
  </div>
</template>

<style scoped>
.outline-editor {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-bg-surface);
  overflow: hidden;
}

.outline-header {
  padding: 20px 24px 12px;
  border-bottom: 1px solid var(--color-border);
}

.outline-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 4px;
}

.outline-hint {
  font-size: 13px;
  color: var(--color-text-muted);
  margin: 0;
}

.outline-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.outline-item {
  border-bottom: 1px solid var(--color-border);
}

.outline-item:last-child {
  border-bottom: none;
}

/* 查看模式 */
.item-view {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 24px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.item-view:hover {
  background: var(--color-bg);
}

.item-number {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-info-bg);
  color: var(--color-info);
  border-radius: 50%;
  font-size: 13px;
  font-weight: 600;
  margin-top: 2px;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 4px;
}

.item-summary {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.5;
}

.item-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.item-view:hover .item-actions {
  opacity: 1;
}

.edit-icon {
  font-size: 16px;
  color: var(--color-text-muted);
  padding-top: 2px;
}

/* 编辑模式 */
.item-edit {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 24px;
  background: var(--color-bg);
}

.edit-fields {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.edit-input,
.edit-textarea {
  width: 100%;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--color-text);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
}

.edit-input:focus,
.edit-textarea:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-soft);
}

.edit-textarea {
  resize: vertical;
}

.edit-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}

.btn-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-surface);
  cursor: pointer;
  font-size: 14px;
  transition: background var(--transition-fast);
}

.btn-save {
  color: var(--color-success);
  border-color: var(--color-success);
}

.btn-save:hover {
  background: var(--color-success-bg);
}

.btn-cancel {
  color: var(--color-error);
  border-color: var(--color-error);
}

.btn-cancel:hover {
  background: var(--color-error-bg);
}

.btn-delete {
  color: var(--color-error);
  border-color: var(--color-error);
  opacity: 1;
}

.btn-delete:hover {
  background: var(--color-error-bg);
}

/* 底部按钮 */
.outline-footer {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg);
}

.btn {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background var(--transition-normal), opacity var(--transition-fast);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.btn-secondary {
  background: var(--color-bg-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg);
}
</style>
