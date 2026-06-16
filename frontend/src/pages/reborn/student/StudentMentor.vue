<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Mentor Connect</p>
      <h2>导师资源与申请进度</h2>
      <p>先匹配导师，再跟踪申请状态，形成清晰协作链路。</p>
    </section>

    <section class="panel">
      <h3>导师列表</h3>
      <div class="toolbar">
        <input v-model.trim="teacherKeyword" type="text" placeholder="搜索导师姓名/方向" @input="onTeacherFilterChange">
      </div>
      <AsyncState :loading="loading" :error="error" :empty="!pagedTeachers.length" empty-text="暂无导师数据" @retry="loadData">
        <div class="mentor-grid">
          <article v-for="item in pagedTeachers" :key="item.id || item.username" class="mentor-card">
            <div>
              <strong>{{ item.name || item.username || '导师' }}</strong>
              <p>专业：{{ item.major || item.specialty || '-' }}</p>
              <p>联系方式：{{ item.phone || item.mobile || item.email || '-' }}</p>
            </div>
            <button type="button" class="primary" @click="openApplyDialog(item)">提交申请</button>
          </article>
        </div>
        <SimplePager :current-page="teacherPage" :total="teachersServerTotal" :page-size="pageSize" @update:currentPage="onTeacherPageChange" />
      </AsyncState>
    </section>

    <section class="panel">
      <h3>申请记录</h3>
      <div class="toolbar">
        <input v-model.trim="applicationKeyword" type="text" placeholder="按导师关键词筛选" @input="onApplicationFilterChange">
        <select v-model="status" @change="onApplicationFilterChange">
          <option value="">全部状态</option>
          <option value="pending">pending</option>
          <option value="approved">approved</option>
          <option value="rejected">rejected</option>
        </select>
      </div>
      <AsyncState :loading="loading" :error="error" :empty="!displayApplications.length" empty-text="暂无申请记录" @retry="loadData">
        <ul>
          <li v-for="item in displayApplications" :key="item.id || item.created_at">
            {{ item.teacher_name || item.teacher || '导师' }} - {{ item.status || 'pending' }}
          </li>
        </ul>
        <SimplePager :current-page="applicationPage" :total="applicationsServerTotal" :page-size="pageSize" @update:currentPage="onApplicationPageChange" />
      </AsyncState>
    </section>

    <div v-if="applyDialogVisible" class="modal-mask" @click.self="closeApplyDialog">
      <section class="modal-card">
        <h3>提交导师申请</h3>
        <p class="hint">向 {{ selectedTeacher?.name || selectedTeacher?.username || '导师' }} 发起申请</p>
        <div class="toolbar modal-toolbar">
          <input v-model.trim="form.startup_direction" type="text" placeholder="创业方向">
          <input v-model.trim="form.demand_note" type="text" placeholder="需求说明">
        </div>
        <div class="toolbar modal-actions">
          <button type="button" class="primary" :disabled="submitting" @click="submit">确认提交</button>
          <button type="button" class="ghost" :disabled="submitting" @click="closeApplyDialog">取消</button>
        </div>
        <p v-if="submitHint" class="hint">{{ submitHint }}</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import AsyncState from '../../../components/core/AsyncState.vue';
import SimplePager from '../../../components/core/SimplePager.vue';
import { teacherListApi } from '../../../api/auth';
import { applyMentorApi, listMentorApplicationsApi } from '../../../api/student';
import { compactQuery, normalizePagedResult } from '../../../composables/list';

const teachers = ref([]);
const applications = ref([]);
const loading = ref(false);
const submitting = ref(false);
const error = ref('');

const teacherKeyword = ref('');
const applicationKeyword = ref('');
const status = ref('');

const form = ref({ teacher: '', startup_direction: '', demand_note: '' });
const submitHint = ref('');
const selectedTeacher = ref(null);
const applyDialogVisible = ref(false);

const teacherPage = ref(1);
const applicationPage = ref(1);
const pageSize = 8;
const teachersServerTotal = ref(0);
const applicationsServerTotal = ref(0);

const pagedTeachers = computed(() => teachers.value);
const displayApplications = computed(() => applications.value);

const loadData = async () => {
  loading.value = true;
  error.value = '';
  try {
    const teacherParams = compactQuery({
      page: teacherPage.value,
      page_size: pageSize,
      q: teacherKeyword.value
    });
    const appParams = compactQuery({
      page: applicationPage.value,
      page_size: pageSize,
      q: applicationKeyword.value,
      status: status.value
    });

    const [teacherRes, applicationRes] = await Promise.all([
      teacherListApi(teacherParams),
      listMentorApplicationsApi(appParams)
    ]);

    const normalizedTeachers = normalizePagedResult(teacherRes);
    const normalizedApplications = normalizePagedResult(applicationRes);
    teachers.value = normalizedTeachers.items;
    teachersServerTotal.value = normalizedTeachers.total;
    applications.value = normalizedApplications.items;
    applicationsServerTotal.value = normalizedApplications.total;
  } catch (e) {
    error.value = e?.response?.data?.detail || '导师数据加载失败';
    teachers.value = [];
    applications.value = [];
    teachersServerTotal.value = 0;
    applicationsServerTotal.value = 0;
  } finally {
    loading.value = false;
  }
};

const onTeacherFilterChange = async () => {
  teacherPage.value = 1;
  await loadData();
};

const onApplicationFilterChange = async () => {
  applicationPage.value = 1;
  await loadData();
};

const onTeacherPageChange = async (page) => {
  teacherPage.value = page;
  await loadData();
};

const onApplicationPageChange = async (page) => {
  applicationPage.value = page;
  await loadData();
};

const openApplyDialog = (teacher) => {
  selectedTeacher.value = teacher;
  form.value = {
    teacher: teacher?.id || teacher?.teacher || '',
    startup_direction: '',
    demand_note: ''
  };
  submitHint.value = '';
  applyDialogVisible.value = true;
};

const closeApplyDialog = () => {
  if (submitting.value) return;
  applyDialogVisible.value = false;
  selectedTeacher.value = null;
};

const submit = async () => {
  submitHint.value = '';
  if (!form.value.teacher) {
    submitHint.value = '请先选择导师';
    return;
  }
  if (!form.value.startup_direction || !form.value.demand_note) {
    submitHint.value = '请完善创业方向与需求说明';
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确认向 ${selectedTeacher.value?.name || selectedTeacher.value?.username || '该导师'} 发起申请吗？`,
      '确认申请',
      {
        confirmButtonText: '确认提交',
        cancelButtonText: '取消',
        type: 'info'
      }
    );
  } catch (_) {
    return;
  }

  submitting.value = true;
  try {
    await applyMentorApi({
      teacher: form.value.teacher,
      startup_direction: form.value.startup_direction,
      demand_note: form.value.demand_note
    });
    ElMessage.success('申请已提交，请等待导师审核');
    applyDialogVisible.value = false;
    selectedTeacher.value = null;
    await loadData();
  } catch (e) {
    submitHint.value = e?.response?.data?.message || e?.response?.data?.detail || '提交申请失败';
  } finally {
    submitting.value = false;
  }
};

onMounted(loadData);
</script>

<style scoped>
.page-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  border: 1px solid var(--line-strong);
  background: var(--bg-panel);
  padding: 18px;
}

.lead {
  grid-column: 1 / -1;
}

.kicker {
  margin: 0;
  font-size: 12px;
  color: var(--ink-muted);
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

h2,
h3 {
  margin: 10px 0 0;
  color: var(--ink-title);
  font-family: var(--font-display);
}

.toolbar {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

input,
select {
  flex: 1 1 220px;
  min-width: 0;
  height: var(--control-height);
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 0 10px;
  border-radius: var(--control-radius);
}

button.primary,
button.ghost {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  cursor: pointer;
}

button.primary {
  border: 1px solid var(--ink-title);
  background: var(--ink-title);
  color: var(--bg-main);
}

button.ghost {
  border: 1px solid var(--ink-title);
  background: transparent;
  color: var(--ink-title);
}

.hint {
  margin-top: 10px;
  color: var(--ink-muted);
}

ul {
  margin: 12px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

.mentor-grid {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.mentor-card {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-sm);
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mentor-card p {
  margin: 6px 0 0;
  color: var(--ink-muted);
  font-size: 13px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.45);
}

.modal-card {
  width: min(560px, 100%);
  border: 1px solid var(--line-strong);
  background: var(--bg-panel);
  border-radius: var(--radius-md);
  padding: 16px;
}

.modal-toolbar > input,
.modal-toolbar > select {
  flex: 1 1 100%;
}

.modal-actions {
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}
</style>

