<template>
  <el-alert v-if="message" :title="message" type="error" show-icon :closable="false" />
</template>

<script setup>
defineProps({
  message: { type: String, default: '' }
});
</script>

