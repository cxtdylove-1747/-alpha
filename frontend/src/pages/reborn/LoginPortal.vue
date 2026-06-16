<template>
  <div class="login-root">
    <section class="intro-strip">
      <p class="eyebrow">INNOVATION STUDIO</p>
      <h1>创新创业智能体平台</h1>
      <p class="desc">
        使用学号/工号登录。新用户可先注册学生或教师账号，再进入对应工作台。
      </p>
      <ul class="highlights" aria-label="核心能力">
        <li>智能引导与知识讲解</li>
        <li>竞赛教练协作写作</li>
        <li>评审与溯源诊断</li>
      </ul>
    </section>

    <section class="form-strip">
      <div class="head">
        <p class="tag">Secure Entry</p>
        <h2>账号登录</h2>
      </div>

      <form class="login-form" @submit.prevent="submit">
        <label>
          <span>账号（学号/工号）</span>
          <input v-model.trim="form.username" autocomplete="username" placeholder="例如：20260001 或 T20260001" />
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="form.password"
            autocomplete="current-password"
            type="password"
            placeholder="请输入密码"
          />
        </label>

        <p v-if="localError" class="error-text" role="alert">{{ localError }}</p>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '正在验证...' : '进入系统' }}
        </button>
      </form>

      <div class="quick-area" aria-label="测试账号">
        <button type="button" @click="quick('student')">学生测试账号</button>
        <button type="button" @click="quick('teacher')">教师测试账号</button>
        <button type="button" @click="quick('admin')">管理员测试账号</button>
      </div>

      <div class="register-area">
        <p class="tag">新用户注册</p>
        <button type="button" class="ghost-btn" @click="openRegisterDialog">点击注册</button>
        <p class="hint">学生注册：学号、姓名、书院/学院、邮箱、密码；教师注册：工号、姓名、书院/学院、邮箱、密码。</p>
      </div>
    </section>

    <div v-if="showRegisterDialog" class="modal-mask" @click.self="closeRegisterDialog">
      <section class="modal-card">
        <h3>新用户注册</h3>
        <div class="register-mode-row">
          <button type="button" :class="['mode-btn', { active: registerForm.role === 'student' }]" @click="registerForm.role = 'student'">学生</button>
          <button type="button" :class="['mode-btn', { active: registerForm.role === 'teacher' }]" @click="registerForm.role = 'teacher'">教师</button>
        </div>

        <form class="register-form" @submit.prevent="registerUser">
          <label>
            <span>{{ registerForm.role === 'student' ? '学号' : '工号' }}</span>
            <input v-model.trim="registerForm.account" type="text" :placeholder="registerForm.role === 'student' ? '请输入学号' : '请输入工号'" />
          </label>
          <label>
            <span>姓名</span>
            <input v-model.trim="registerForm.name" type="text" placeholder="请输入姓名" />
          </label>
          <label>
            <span>书院/学院</span>
            <input v-model.trim="registerForm.college" type="text" placeholder="请输入书院或学院" />
          </label>
          <label>
            <span>邮箱</span>
            <input v-model.trim="registerForm.email" type="email" placeholder="请输入邮箱" />
          </label>
          <label>
            <span>设置密码</span>
            <input v-model="registerForm.password" type="password" placeholder="至少 8 位" />
          </label>

          <p v-if="registerTip" class="error-text" role="alert">{{ registerTip }}</p>

          <div class="modal-actions">
            <button type="button" class="ghost-btn" :disabled="registering" @click="closeRegisterDialog">取消</button>
            <button type="submit" class="submit-btn" :disabled="registering">
              {{ registering ? '注册中...' : '确认注册' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { loginApi, registerApi } from '../../api/auth';
import { useAuthStore } from '../../stores/auth';

const router = useRouter();
const auth = useAuthStore();

const loading = ref(false);
const localError = ref('');
const registering = ref(false);
const registerTip = ref('');
const showRegisterDialog = ref(false);

const form = reactive({
  username: '',
  password: ''
});

const registerForm = reactive({
  role: 'student',
  account: '',
  name: '',
  college: '',
  email: '',
  password: ''
});

const quick = (type) => {
  if (type === 'student') {
    form.username = '20260001';
    form.password = 'Student@123';
    return;
  }
  if (type === 'teacher') {
    form.username = 'T20260001';
    form.password = 'Teacher@123';
    return;
  }
  form.username = 'admin';
  form.password = 'Admin@123';
};

const resolveHome = (user) => {
  if (!user) {
    return '/student/home';
  }
  if (user.is_admin || user.is_staff || user.is_superuser || user.role === 'administer') {
    return '/admin/console';
  }
  return user.role === 'teacher' ? '/teacher/home' : '/student/home';
};

const submit = async () => {
  localError.value = '';
  loading.value = true;
  try {
    const payload = await loginApi(form);
    auth.setAuth(payload);
    router.push(resolveHome(payload.user));
  } catch (error) {
    localError.value = error?.response?.data?.message || error?.response?.data?.detail || '登录失败，请检查账号密码';
  } finally {
    loading.value = false;
  }
};

const openRegisterDialog = () => {
  showRegisterDialog.value = true;
  registerTip.value = '';
};

const closeRegisterDialog = () => {
  if (registering.value) return;
  showRegisterDialog.value = false;
};

const resetRegisterForm = () => {
  registerForm.account = '';
  registerForm.name = '';
  registerForm.college = '';
  registerForm.email = '';
  registerForm.password = '';
};

const registerUser = async () => {
  registerTip.value = '';
  if (!registerForm.account || !registerForm.name || !registerForm.college || !registerForm.password) {
    registerTip.value = '请完整填写注册信息';
    return;
  }

  const payload = {
    role: registerForm.role,
    name: registerForm.name,
    college: registerForm.college,
    email: registerForm.email,
    password: registerForm.password
  };
  if (registerForm.role === 'student') {
    payload.student_id = registerForm.account;
  } else {
    payload.teacher_id = registerForm.account;
  }

  registering.value = true;
  try {
    await registerApi(payload);
    form.username = registerForm.account;
    form.password = registerForm.password;
    resetRegisterForm();
    showRegisterDialog.value = false;
    registerTip.value = '';
  } catch (error) {
    registerTip.value = error?.response?.data?.message || error?.response?.data?.detail || '注册失败，请检查信息是否重复';
  } finally {
    registering.value = false;
  }
};
</script>

<style scoped>
.login-root {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(340px, 460px);
  background:
    radial-gradient(980px 460px at 6% 4%, color-mix(in oklch, var(--accent) 26%, transparent), transparent 66%),
    radial-gradient(880px 430px at 102% -6%, color-mix(in oklch, var(--accent-2) 24%, transparent), transparent 62%),
    var(--bg-main);
}

.intro-strip {
  padding: clamp(28px, 6vw, 74px) clamp(20px, 5vw, 66px) clamp(22px, 4vw, 44px);
  border-right: 1px solid color-mix(in oklch, var(--line-soft) 84%, white);
  display: grid;
  align-content: start;
  gap: 20px;
  position: relative;
}

.intro-strip::after {
  content: '';
  position: absolute;
  inset: 16px 16px auto auto;
  width: 96px;
  height: 96px;
  border-radius: 28px;
  background:
    linear-gradient(145deg, color-mix(in oklch, var(--accent) 82%, white), color-mix(in oklch, var(--accent-2) 62%, white));
  opacity: 0.18;
  transform: rotate(14deg);
  pointer-events: none;
}

.eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  font-size: 12px;
  color: var(--ink-muted);
}

.intro-strip h1 {
  margin: 0;
  max-width: 15ch;
  font-family: var(--font-display);
  font-size: clamp(36px, 5.6vw, 76px);
  line-height: 1.04;
  letter-spacing: 0.02em;
  color: var(--ink-title);
}

.desc {
  margin: 0;
  max-width: 62ch;
  color: var(--ink-body);
  font-size: 15px;
}

.highlights {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
}

.highlights li {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-body);
  font-size: 14px;
  width: fit-content;
  border: 1px solid color-mix(in oklch, var(--line-soft) 76%, white);
  background: color-mix(in oklch, var(--bg-panel) 80%, white);
  border-radius: 999px;
  padding: 6px 12px 6px 10px;
}

.highlights li::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent) 32%, transparent);
}

.form-strip {
  margin: clamp(14px, 2.4vw, 22px);
  padding: clamp(24px, 3.8vw, 42px);
  border: 1px solid color-mix(in oklch, var(--line-soft) 80%, white);
  border-radius: 24px;
  background:
    linear-gradient(158deg, color-mix(in oklch, var(--accent) 10%, white), color-mix(in oklch, var(--bg-panel) 98%, white)),
    var(--bg-panel);
  box-shadow: var(--shadow-mid);
  display: grid;
  align-content: center;
  gap: 20px;
  backdrop-filter: blur(8px);
}

.head .tag {
  margin: 0;
  color: var(--ink-muted);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-size: 12px;
}

.head h2 {
  margin: 8px 0 0;
  font-family: var(--font-display);
  font-size: clamp(30px, 3.2vw, 38px);
  color: var(--ink-title);
}

.login-form {
  display: grid;
  gap: 14px;
}

label {
  display: grid;
  gap: 8px;
  color: var(--ink-body);
  font-size: 14px;
}

input {
  height: 46px;
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  padding: 0 13px;
  color: var(--ink-title);
  border-radius: 12px;
}

input:focus {
  outline: none;
  box-shadow: var(--shadow-focus);
  border-color: var(--accent);
}

.submit-btn {
  min-height: 46px;
  border: 1px solid var(--accent);
  background: linear-gradient(145deg, color-mix(in oklch, var(--accent) 86%, white), var(--accent));
  color: #fff;
  cursor: pointer;
  margin-top: 4px;
  border-radius: 999px;
  font-weight: 650;
  letter-spacing: 0.03em;
  transition: transform var(--motion-fast) ease, box-shadow var(--motion-mid) ease;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px color-mix(in oklch, var(--accent) 34%, transparent);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-text {
  margin: 0;
  color: var(--danger);
  font-size: 13px;
}

.quick-area {
  display: grid;
  gap: 9px;
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
}

.quick-area button {
  min-height: 38px;
  border: 1px solid var(--line-strong);
  background: color-mix(in oklch, var(--bg-field) 86%, white);
  color: var(--ink-body);
  cursor: pointer;
  border-radius: 12px;
  font-weight: 560;
}

.quick-area button:hover {
  border-color: color-mix(in oklch, var(--accent) 64%, var(--line-strong));
  background: color-mix(in oklch, var(--accent) 12%, white);
  color: var(--ink-title);
  transform: translateY(-1px);
}

.register-area {
  border-top: 1px dashed color-mix(in oklch, var(--line-soft) 76%, white);
  padding-top: 14px;
  display: grid;
  gap: 8px;
}

.ghost-btn {
  height: 38px;
  border: 1px solid var(--line-strong);
  background: color-mix(in oklch, var(--bg-field) 86%, white);
  color: var(--ink-body);
  cursor: pointer;
  border-radius: 999px;
}

.ghost-btn:hover {
  border-color: color-mix(in oklch, var(--accent) 50%, var(--line-strong));
  background: color-mix(in oklch, var(--accent) 9%, white);
}

.hint {
  margin: 0;
  color: var(--ink-muted);
  font-size: 12px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(4px);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.modal-card {
  width: min(640px, 100%);
  border: 1px solid color-mix(in oklch, var(--line-soft) 72%, var(--line-strong));
  background:
    linear-gradient(155deg, color-mix(in oklch, var(--accent) 9%, white), color-mix(in oklch, var(--bg-panel) 98%, white));
  border-radius: 22px;
  padding: 20px;
  display: grid;
  gap: 14px;
  box-shadow: var(--shadow-mid);
}

.modal-card h3 {
  margin: 0;
  color: var(--ink-title);
  font-family: var(--font-display);
}

.register-mode-row {
  display: flex;
  gap: 8px;
}

.mode-btn {
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid var(--line-strong);
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  color: var(--ink-body);
  cursor: pointer;
  border-radius: 999px;
}

.mode-btn.active {
  border-color: var(--accent);
  color: #fff;
  background: var(--accent);
}

.register-form {
  display: grid;
  gap: 12px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

@media (max-width: 980px) {
  .login-root {
    grid-template-columns: 1fr;
  }

  .intro-strip {
    border-right: none;
    border-bottom: 1px solid color-mix(in oklch, var(--line-soft) 92%, white);
    padding-bottom: 22px;
  }

  .form-strip {
    margin: 12px;
    border-radius: 16px;
  }
}
</style>
