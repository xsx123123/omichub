import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory, RouterView, RouterLink } from 'vue-router'
import { NMessageProvider, NDialogProvider } from 'naive-ui'
import Home from './src/views/HomeView.vue'
import Treasure from './src/views/TreasureMouseView.vue'
import Flows from './src/views/FlowsView.vue'
import About from './src/views/AboutView.vue'
import { useAuthStore } from './src/stores/auth'
import './src/styles/tokens.css'
import './src/styles/global.css'
const app = createApp({render:()=>h(NMessageProvider, null, {default:()=>h(NDialogProvider,null,{default:()=>[
 h('nav',{style:'display:flex;gap:24px;height:44px;align-items:center;padding:0 24px'},[h(RouterLink,{to:'/'},{default:()=> '首页'}),h(RouterLink,{to:'/flows'},{default:()=> '分析中心'})]),
 h('div',{style:'height:calc(100vh - 44px)'},h(RouterView)),
]})})})
app.use(createPinia())
app.use(createRouter({history:createWebHashHistory(),routes:[{path:'/about',name:'about',component:About},{path:'/',name:'home',component:Home},{path:'/treasure-mouse',name:'treasure-mouse',component:Treasure},{path:'/flows',name:'flows',component:Flows},...['projects','tasks','reports'].map(name=>({name,path:'/'+name,component:Home}))]}))
useAuthStore().user = {username:'JIAN',nickname:'JIAN',role:'admin'} as any
app.mount('#app')
