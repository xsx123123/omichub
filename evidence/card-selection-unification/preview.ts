import { createApp, h, ref } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import { NMessageProvider, NDialogProvider } from 'naive-ui'
import Home from './src/views/HomeView.vue'
import ImageSelector from './src/components/terminal/ImageSelector.vue'
import AgentCard from './src/components/agent-workspace/AgentCard.vue'
import { useAuthStore } from './src/stores/auth'
import './src/styles/tokens.css'
import './src/styles/global.css'
import './src/styles/chat-theme.css'
const selectedImage = ref('one')
const agentSelected = ref(false)
const images=[{id:'one',name:'镜像一',description:'已选镜像',icon:'A',tags:[],resources:{memory_mb:4096,cpu_cores:2}},{id:'two',name:'镜像二',description:'可选镜像',icon:'B',tags:[],resources:{memory_mb:4096,cpu_cores:2}}]
const agent={id:'test',name:'测试智能体',avatar:'A',color:'#8059d8',category:'analysis',mcp_ids:[],skill_ids:[],description:'共享卡片样式验证'}
const app=createApp({render:()=>h(NMessageProvider,null,{default:()=>h(NDialogProvider,null,{default:()=>[
 h(Home),h('section',{id:'shared-regression',style:'padding:24px'},[
 h(ImageSelector,{images,modelValue:selectedImage.value,'onUpdate:modelValue':(value:string)=>selectedImage.value=value}),
 h(AgentCard,{agent,class:{'is-highlighted':agentSelected.value},onSelect:()=>agentSelected.value=true}),
 h('div',{class:'model-switcher-panel'},h('div',{class:'model-item cygnusx-selectable-card is-selected'},'模型选项')),
 ])]})})})
app.use(createPinia())
const router=createRouter({history:createWebHashHistory(),routes:[...['projects','tasks','flows','reports','treasure-mouse','about'].map(name=>({name,path:'/'+name,component:Home})),{path:'/',component:Home}]})
router.beforeEach(to=>to.path==='/' ? true : false)
app.use(router)
useAuthStore().user={username:'JIAN',role:'user'} as any
app.mount('#app')
