import { createRouter, createWebHistory } from 'vue-router'
import { whoami } from '../api'

import Login from '../views/Login.vue'
import Home from '../views/Home.vue'
import Upload from '../views/Upload.vue'
import Planning from '../views/Planning.vue'
import GapStat from '../views/GapStat.vue'
import QualityInspection from '../views/QualityInspection.vue'
import QualityMaterial from '../views/QualityMaterial.vue'
import QualityTools from '../views/QualityTools.vue'
import Inventory from '../views/Inventory.vue'
import InventoryOverview from '../views/InventoryOverview.vue'
import InventoryShare from '../views/InventoryShare.vue'
import InventoryDetail from '../views/InventoryDetail.vue'
import InventoryGap from '../views/InventoryGap.vue'
import MaterialGap from '../views/MaterialGap.vue'
import Knowledge from '../views/Knowledge.vue'
import KnowledgeManage from '../views/KnowledgeManage.vue'
import AgentChat from '../views/AgentChat.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    {
      path: '/',
      component: Home,
      children: [
        { path: '', redirect: '/knowledge' },
        { path: 'knowledge', name: 'knowledge', component: Knowledge },
        { path: 'knowledge-manage', name: 'knowledge-manage', component: KnowledgeManage },
        { path: 'agent-chat', name: 'agent-chat', component: AgentChat },
        { path: 'upload', name: 'upload', component: Upload },
        { path: 'planning', name: 'planning', component: Planning },
        { path: 'gap-stat', name: 'gap-stat', component: GapStat },
        { path: 'quality', name: 'quality', redirect: '/quality/inspection' },
        { path: 'quality/inspection', name: 'quality-inspection', component: QualityInspection },
        { path: 'quality/material', name: 'quality-material', component: QualityMaterial },
        { path: 'quality/tools', name: 'quality-tools', component: QualityTools },
        { path: 'inventory', name: 'inventory', component: InventoryOverview },
        { path: 'inventory/overview', name: 'inventory-overview', component: InventoryOverview },
        { path: 'inventory/share', name: 'inventory-share', component: InventoryShare },
        { path: 'inventory/detail', name: 'inventory-detail', component: InventoryDetail },
        { path: 'inventory/gap', name: 'inventory-gap', component: InventoryGap },
        { path: 'inventory/material-gap', name: 'inventory-material-gap', component: MaterialGap },
      ],
    },
  ],
})

// 全局前置守卫：未登录跳转登录页
router.beforeEach(async (to) => {
  if (to.path === '/login') return true
  try {
    await whoami()
    return true
  } catch {
    return { name: 'login' }
  }
})

export default router
