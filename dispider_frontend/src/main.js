import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import './styles/main.scss'
import router from './router'
import { useAuthStore } from './stores/auth';

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(ElementPlus)

// This must be done after Pinia is installed
const authStore = useAuthStore();
authStore.tryAutoLogin();

app.use(router)
app.mount('#app')
