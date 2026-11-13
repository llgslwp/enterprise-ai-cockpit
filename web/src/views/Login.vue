<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    await login(username.value, password.value)
    router.push('/')
  } catch (e) {
    // 后端约定 { code, message, data } 结构，真实原因在 message 字段
    error.value = e.response?.data?.message || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card">
      <h1>企业 AI 驾驶舱</h1>
      <p class="sub">制造业 × Agent 智能运营平台</p>
      <form @submit.prevent="onSubmit">
        <label>
          账号
          <input v-model="username" type="text" autocomplete="username" />
        </label>
        <label>
          密码
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>
        <p v-if="error" class="err">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-background-tertiary, #f5f5f5);
}
.login-card {
  width: 360px;
  padding: 40px 32px;
  background: var(--color-background-primary, #fff);
  border: 1px solid var(--color-border-tertiary, #e5e5e5);
  border-radius: 12px;
}
h1 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  text-align: center;
}
.sub {
  text-align: center;
  color: var(--color-text-secondary, #666);
  margin: 8px 0 28px;
}
label {
  display: block;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-secondary, #666);
}
input {
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 10px 12px;
  font-size: 14px;
  border: 1px solid var(--color-border-tertiary, #ddd);
  border-radius: 8px;
  box-sizing: border-box;
}
.err {
  color: var(--color-text-danger, #d32f2f);
  font-size: 13px;
  margin: 0 0 12px;
}
button {
  width: 100%;
  padding: 11px;
  font-size: 14px;
  border: none;
  border-radius: 8px;
  background: var(--color-text-primary, #222);
  color: var(--color-background-primary, #fff);
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
