<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { logout } from '../api'

const router = useRouter()
const route = useRoute()

const navs = [
  { path: '/knowledge', label: '知识库' },
  { path: '/knowledge-manage', label: '知识管理' },
  { path: '/agent-chat', label: '智能辅助决策' },
  { path: '/upload', label: '文件上传' },
  { label: '生产管理', children: [
    { path: '/planning', label: '生产计划' },
    { path: '/gap-stat', label: '缺口统计' },
  ] },
  { label: '供应链管理', children: [
    { path: '/inventory/overview', label: '成品总览' },
    { path: '/inventory/share', label: '成品占比' },
    { path: '/inventory/detail', label: '重点成品' },
    { label: '库存预警', children: [
      { path: '/inventory/gap', label: '成品预警' },
      { path: '/inventory/material-gap', label: '原料预警' },
    ] },
  ] },
  { label: '质量管理', children: [
    { path: '/quality/inspection', label: '生产巡检' },
    { path: '/quality/material', label: '原料检验' },
    { path: '/quality/tools', label: '质量管理工具' },
  ] },
]

const groupOpen = ref({})

// 每个分组对应一个或多个路由前缀，用于判断高亮
const GROUP_PREFIX = {
  '生产管理': ['/planning', '/gap-stat'],
  '供应链管理': ['/inventory'],
  '库存预警': ['/inventory/gap', '/inventory/material-gap'],
  '质量管理': ['/quality'],
}

function groupActive(n) {
  const prefixes = GROUP_PREFIX[n.label]
  if (!prefixes) return false
  return prefixes.some(p => route.path.startsWith(p))
}

function toggleGroup(n) {
  groupOpen.value[n.label] = !groupOpen.value[n.label]
}

async function onLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">企业 AI 驾驶舱</div>
      <nav>
        <template v-for="n in navs" :key="n.label">
          <!-- 普通菜单项 -->
          <router-link
            v-if="n.path"
            :to="n.path"
            class="nav-item"
          >{{ n.label }}</router-link>
          <!-- 带子菜单的项 -->
          <div v-else class="nav-group">
            <button
              class="nav-item nav-parent"
              :class="{ 'group-active': groupActive(n) }"
              @click="toggleGroup(n)"
            >
              <span>{{ n.label }}</span>
              <span class="arrow" :class="{ open: groupOpen[n.label] }">▸</span>
            </button>
            <div v-show="groupOpen[n.label]" class="nav-children">
              <template v-for="c in n.children" :key="c.label || c.path">
                <!-- 二级叶子项 -->
                <router-link
                  v-if="c.path"
                  :to="c.path"
                  class="nav-item nav-child"
                >{{ c.label }}</router-link>
                <!-- 二级分组（如「库存预警」） -->
                <div v-else class="nav-group">
                  <button
                    class="nav-item nav-child nav-parent"
                    :class="{ 'group-active': groupActive(c) }"
                    @click="toggleGroup(c)"
                  >
                    <span>{{ c.label }}</span>
                    <span class="arrow" :class="{ open: groupOpen[c.label] }">▸</span>
                  </button>
                  <div v-show="groupOpen[c.label]" class="nav-children">
                    <router-link
                      v-for="g in c.children"
                      :key="g.path"
                      :to="g.path"
                      class="nav-item nav-child"
                    >{{ g.label }}</router-link>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>
      </nav>
      <button class="logout" @click="onLogout">退出登录</button>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 200px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0) 12%),
    linear-gradient(180deg, #4d4d4d 0%, #383838 45%, #2b2b2b 100%);
  border-right: 1px solid #4a4a4a;
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
  color: #d6d6d6;
}
.brand {
  font-size: 15px;
  font-weight: 600;
  padding: 0 8px 20px;
  color: #ececec;
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.4);
}
nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-item {
  padding: 10px 12px;
  border-radius: 8px;
  color: #c6c6c6;
  text-decoration: none;
  font-size: 14px;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #eaeaea;
}
.nav-item.router-link-active {
  background: linear-gradient(180deg, #5a5a5a 0%, #474747 100%);
  color: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}
.nav-group { display: flex; flex-direction: column; }
.nav-parent {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  border: none; background: transparent; text-align: left;
}
.nav-parent.group-active {
  color: #f0f0f0;
  font-weight: 600;
}
.nav-parent .arrow { transition: transform .2s; font-size: 12px; }
.nav-parent .arrow.open { transform: rotate(90deg); }
.nav-children {
  display: flex; flex-direction: column;
  padding-left: 12px; margin-top: 2px;
}
.nav-child { font-size: 13px; padding: 8px 12px; }
.logout {
  margin-top: 12px;
  padding: 9px;
  border: 1px solid #4a4a4a;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  font-size: 13px;
  color: #c6c6c6;
}
.logout:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}
.content {
  flex: 1;
  padding: 24px;
}
</style>
