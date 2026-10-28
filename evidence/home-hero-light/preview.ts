import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { NMessageProvider, NDialogProvider } from 'naive-ui'
import Home from './src/views/HomeView.vue'
import { useAuthStore } from './src/stores/auth'
import './src/styles/tokens.css'
import './src/styles/global.css'
const app = createApp({render:()=>h(NMessageProvider, null, {default:()=>h(NDialogProvider,null,{default:()=>h(Home)})})})
app.use(createPinia())
app.use(createRouter({history:createWebHistory(),routes:[...['projects','tasks','flows','reports'].map(name=>({name,path:'/'+name,component:Home})),{path:'/:pathMatch(.*)*',component:Home}]}))
useAuthStore().user = {username:'JIAN',nickname:'JIAN',role:'user'} as any
app.mount('#app')
