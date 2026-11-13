<template>
  <span
    class="visio-icon-wrap"
    :style="{ width: `${dimension}px`, height: `${dimension}px` }"
    :data-type="type"
    v-html="svgHtml"
  />
</template>

<script setup>
import { computed } from 'vue'
import { getVisioSvg } from '../utils/visioIcons'

const props = defineProps({
  type: {
    type: String,
    default: 'default',
  },
  size: {
    type: [Number, String],
    default: 16,
  },
})

const dimension = computed(() => {
  const num = parseInt(props.size, 10)
  return isNaN(num) ? 16 : num
})

const svgHtml = computed(() => {
  return getVisioSvg(props.type)
})
</script>

<style scoped>
.visio-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
  line-height: 1;
  flex-shrink: 0;
}
.visio-icon-wrap :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
