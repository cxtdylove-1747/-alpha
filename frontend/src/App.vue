<template>
  <RouterView v-if="isPublicRoute" />

  <AppShell
    v-else
    :user="auth.user"
    :role-label="roleLabel"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :nav-items="navItems"
    @logout="handleLogout"
  >
    <RouterView />
  </AppShell>

  <TransitionGroup name="toast-fade" tag="div" class="toast-stack">
    <div v-for="toast in toasts" :key="toast.id" class="toast-item" :class="toast.type">{{ toast.message }}</div>
  </TransitionGroup>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterView, useRoute, useRouter } from 'vue-router';
import { ElMessageBox } from 'element-plus';
import { profileApi } from './api/auth';
import AppShell from './components/core/AppShell.vue';
import { useAuthStore } from './stores/auth';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const toasts = ref([]);

const resolveRole = (user) => {
  if (!user) {
    return 'guest';
  }
  if (user.is_admin || user.is_staff || user.is_superuser || user.role === 'administer') {
    return 'admin';
  }
  return user.role === 'teacher' ? 'teacher' : 'student';
};

const role = computed(() => resolveRole(auth.user));
const roleLabel = computed(() => {
  if (role.value === 'admin') return '系统管理员';
  if (role.value === 'teacher') return '教师';
  if (role.value === 'student') return '学生';
  return '访客';
});

const navByRole = {
  student: [
    { label: '智能引导', path: '/student/home' },
    { label: '方案管理', path: '/student/plan' },
    { label: '路演优化', path: '/student/pitch' },
    { label: '财务设计', path: '/student/finance' },
    { label: '竞赛教练', path: '/student/competition' },
    { label: '教师连接', path: '/student/mentor' },
    { label: '个人档案', path: '/student/profile' }
  ],
  teacher: [
    { label: '总览', path: '/teacher/home' },
    { label: '学生管理', path: '/teacher/students' },
    { label: '评审中心', path: '/teacher/reviews' },
    { label: '备课助手', path: '/teacher/prep' }
  ],
  admin: [
    { label: '运营控制台', path: '/admin/console' }
  ]
};

const navItems = computed(() => navByRole[role.value] || []);
const isPublicRoute = computed(() => Boolean(route.meta.public));
const pageTitle = computed(() => route.meta.title || '创新创业智能体平台');
const pageSubtitle = computed(() => route.meta.subtitle || '面向项目全周期的协同工作台');

const pushToast = (message, type = 'error') => {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  toasts.value.push({ id, message, type });
  setTimeout(() => {
    toasts.value = toasts.value.filter((item) => item.id !== id);
  }, 2400);
};

const onNotify = (event) => {
  const message = event?.detail?.message;
  if (typeof message !== 'string' || !message.trim()) {
    return;
  }
  pushToast(message, event?.detail?.type || 'error');
};

const closeTransientOverlays = () => {
  try {
    ElMessageBox.close();
  } catch (_) {
    // ignore
  }
  document.querySelectorAll('.el-overlay, .v-modal').forEach((node) => node.remove());
  document.body.classList.remove('el-popup-parent--hidden');
};

const restoreSession = async () => {
  if (!auth.accessToken || auth.user) {
    return;
  }
  try {
    const profile = await profileApi();
    auth.setUser(profile);
  } catch (_) {
    auth.clearAuth();
    if (!route.meta.public) {
      router.replace('/login');
    }
  }
};

const handleLogout = () => {
  closeTransientOverlays();
  auth.clearAuth();
  router.push('/login');
};

onMounted(() => {
  window.addEventListener('app:notify', onNotify);
  restoreSession();
});

onBeforeUnmount(() => {
  window.removeEventListener('app:notify', onNotify);
});

watch(
  () => route.path,
  (path) => {
    if (path === '/login') {
      closeTransientOverlays();
    }
  }
);

watch(
  [role, isPublicRoute],
  ([nextRole, isPublic]) => {
    if (isPublic) {
      document.body.removeAttribute('data-app-role');
      return;
    }
    document.body.setAttribute('data-app-role', nextRole);
  },
  { immediate: true }
);
</script>
