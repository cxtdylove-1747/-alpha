import { createRouter, createWebHashHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import LoginPortal from '../pages/reborn/LoginPortal.vue';
import AdminNexus from '../pages/reborn/AdminNexus.vue';
import StudentHome from '../pages/reborn/student/StudentHome.vue';
import StudentPlan from '../pages/reborn/student/StudentPlan.vue';
import StudentPitch from '../pages/reborn/student/StudentPitch.vue';
import StudentFinance from '../pages/reborn/student/StudentFinance.vue';
import StudentCompetition from '../pages/reborn/student/StudentCompetitionCoach.vue';
import StudentMentor from '../pages/reborn/student/StudentMentor.vue';
import StudentProfile from '../pages/reborn/student/StudentProfile.vue';
import TeacherHome from '../pages/reborn/teacher/TeacherHome.vue';
import TeacherStudents from '../pages/reborn/teacher/TeacherStudents.vue';
import TeacherReviews from '../pages/reborn/teacher/TeacherReviews.vue';
import TeacherPrep from '../pages/reborn/teacher/TeacherPrep.vue';

const routes = [
  {
    path: '/login',
    component: LoginPortal,
    meta: { public: true, title: '欢迎登录创新创业智能体平台', subtitle: '输入学号/工号与密码，按角色进入工作台' }
  },
  {
    path: '/',
    redirect: '/login'
  },

  { path: '/student/home', component: StudentHome, meta: { roles: ['student'], title: '智能引导', subtitle: '在同一个智能体中完成项目引导与知识学习' } },
  { path: '/student/plan', component: StudentPlan, meta: { roles: ['student'], title: '方案管理', subtitle: '版本演进、证据沉淀与结构化迭代' } },
  { path: '/student/review', redirect: '/student/plan' },
  { path: '/student/pitch', component: StudentPitch, meta: { roles: ['student'], title: '路演优化', subtitle: '围绕路演模拟打磨表达、证据与应答策略' } },
  { path: '/student/finance', component: StudentFinance, meta: { roles: ['student'], title: '财务设计', subtitle: '生成盈利/融资方案并量化关键财务假设' } },
  { path: '/student/competition', component: StudentCompetition, meta: { roles: ['student'], title: '竞赛教练', subtitle: '协作撰写计划书并按赛道给出修改建议' } },
  { path: '/student/knowledge', redirect: '/student/home' },
  { path: '/student/mentor', component: StudentMentor, meta: { roles: ['student'], title: '教师连接', subtitle: '把求助变成高质量协作输入' } },
  { path: '/student/profile', component: StudentProfile, meta: { roles: ['student'], title: '个人档案', subtitle: '记录成长轨迹，形成长期能力证据' } },

  { path: '/teacher/home', component: TeacherHome, meta: { roles: ['teacher'], title: '教师驾驶舱', subtitle: '先看班级总览，再定位干预优先级' } },
  { path: '/teacher/analytics', redirect: '/teacher/home' },
  { path: '/teacher/students', component: TeacherStudents, meta: { roles: ['teacher'], title: '学生管理', subtitle: '快速定位需要额外支持的学生与项目' } },
  { path: '/teacher/reviews', component: TeacherReviews, meta: { roles: ['teacher'], title: '评审中心', subtitle: '构建一致且可解释的评价基线' } },
  { path: '/teacher/prep', component: TeacherPrep, meta: { roles: ['teacher'], title: '备课助手', subtitle: '基于真实问题反哺课程内容设计' } },

  { path: '/admin/console', component: AdminNexus, meta: { roles: ['admin'], title: '管理员控制台', subtitle: '监控平台运行状态与账号健康度' } },
  { path: '/:pathMatch(.*)*', redirect: '/login' }
];

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes
});

const resolveRole = (user) => {
  if (!user) {
    return '';
  }
  if (user.is_admin || user.is_staff || user.is_superuser || user.role === 'administer') {
    return 'admin';
  }
  return user.role;
};

const resolveHome = (user) => {
  const role = resolveRole(user);
  if (role === 'admin') {
    return '/admin/console';
  }
  if (role === 'teacher') {
    return '/teacher/home';
  }
  return '/student/home';
};

router.beforeEach((to) => {
  const auth = useAuthStore();
  const role = resolveRole(auth.user);

  if (to.meta.public) {
    if (auth.accessToken && auth.user && to.path === '/login') {
      return resolveHome(auth.user);
    }
    return true;
  }

  if (!auth.accessToken) {
    return '/login';
  }

  const allowedRoles = to.meta.roles || [];
  if (auth.user && allowedRoles.length && !allowedRoles.includes(role)) {
    return resolveHome(auth.user);
  }

  return true;
});

export default router;
