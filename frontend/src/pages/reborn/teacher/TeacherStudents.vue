<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Student Management</p>
      <h2>申请审批与学生绑定管理</h2>
      <p>先处理指导申请，再按学生列表进行检索、状态确认与解绑操作。</p>
    </section>

    <section class="panel list-panel">
      <h3>申请列表</h3>
      <div class="toolbar">
        <input v-model.trim="keyword" type="text" placeholder="按学生或方向搜索" @input="onFilterChange">
        <select v-model="status" @change="onFilterChange">
          <option value="">全部状态</option>
          <option value="pending">待处理</option>
          <option value="approved">已通过</option>
          <option value="rejected">已拒绝</option>
        </select>
      </div>
      <AsyncState :loading="loading" :error="error" :empty="!displayApplications.length" empty-text="暂无申请" @retry="loadApplications">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>导师</th>
                <th>方向</th>
                <th>状态</th>
                <th>审批</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in displayApplications" :key="item.id || item.created_at">
                <td>{{ item.student_name || item.student || '-' }}</td>
                <td>{{ item.teacher_name || item.teacher || '-' }}</td>
                <td>{{ item.startup_direction || '-' }}</td>
                <td>
                  <span class="status-chip" :class="statusClass(item.status)">
                    {{ statusText(item.status) }}
                  </span>
                </td>
                <td class="actions">
                  <button
                    type="button"
                    class="ghost"
                    :disabled="item.status !== 'pending' || auditLoadingId === item.id"
                    @click="audit(item, 'approve')"
                  >
                    通过
                  </button>
                  <button
                    type="button"
                    class="ghost danger"
                    :disabled="item.status !== 'pending' || auditLoadingId === item.id"
                    @click="audit(item, 'reject')"
                  >
                    拒绝
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <SimplePager :current-page="currentPage" :total="displayTotal" :page-size="pageSize" @update:currentPage="onPageChange" />
      </AsyncState>
    </section>

    <section class="panel list-panel">
      <h3>学生列表</h3>
      <div class="toolbar">
        <input v-model.trim="studentKeyword" type="text" placeholder="搜索学生姓名/学号/专业" @input="onStudentFilterChange">
      </div>
      <AsyncState :loading="studentLoading" :error="studentError" :empty="!studentRows.length" empty-text="暂无已绑定学生" @retry="loadStudents">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>学号</th>
                <th>专业</th>
                <th>状态</th>
                <th>绑定时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in studentRows" :key="`st-${item.student_id}`">
                <td>{{ item.student_name || item.username || '-' }}</td>
                <td>{{ item.student_no || '-' }}</td>
                <td>{{ item.major || '-' }}</td>
                <td>
                  <span class="status-chip" :class="item.status === 'bound' ? 'status-approved' : 'status-rejected'">
                    {{ item.status_text || (item.status === 'bound' ? '已绑定' : '未绑定') }}
                  </span>
                </td>
                <td>{{ formatDateTime(item.bound_at) }}</td>
                <td class="actions">
                  <button
                    type="button"
                    class="ghost danger"
                    :disabled="item.status !== 'bound' || unbindLoadingId === item.student_id"
                    @click="unbindStudent(item)"
                  >
                    解绑
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <SimplePager :current-page="studentPage" :total="studentTotal" :page-size="studentPageSize" @update:currentPage="onStudentPageChange" />
      </AsyncState>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessageBox } from 'element-plus';
import AsyncState from '../../../components/core/AsyncState.vue';
import SimplePager from '../../../components/core/SimplePager.vue';
import {
  auditApplicationApi,
  listApplicationsApi,
  listTeacherStudentsApi,
  unbindTeacherStudentApi
} from '../../../api/teacher';
import { compactQuery, normalizePagedResult } from '../../../composables/list';
import { formatDateTime } from '../../../utils/datetime';

const applications = ref([]);
const loading = ref(false);
const error = ref('');
const keyword = ref('');
const status = ref('');
const currentPage = ref(1);
const pageSize = 8;
const serverTotal = ref(0);
const auditLoadingId = ref(0);

const studentRows = ref([]);
const studentLoading = ref(false);
const studentError = ref('');
const studentKeyword = ref('');
const studentPage = ref(1);
const studentPageSize = 10;
const studentTotal = ref(0);
const unbindLoadingId = ref(0);

const displayApplications = computed(() => applications.value);
const displayTotal = computed(() => serverTotal.value);

const statusText = (value) => {
  if (value === 'approved') return '已通过';
  if (value === 'rejected') return '已拒绝';
  return '待处理';
};
const statusClass = (value) => {
  if (value === 'approved') return 'status-approved';
  if (value === 'rejected') return 'status-rejected';
  return 'status-pending';
};

const loadApplications = async () => {
  loading.value = true;
  error.value = '';
  try {
    const params = compactQuery({
      page: currentPage.value,
      page_size: pageSize,
      q: keyword.value,
      status: status.value
    });
    const res = await listApplicationsApi(params);
    const normalized = normalizePagedResult(res);
    applications.value = normalized.items;
    serverTotal.value = normalized.total;
  } catch (e) {
    error.value = e?.response?.data?.detail || '申请列表加载失败';
    applications.value = [];
    serverTotal.value = 0;
  } finally {
    loading.value = false;
  }
};

const loadStudents = async () => {
  studentLoading.value = true;
  studentError.value = '';
  try {
    const params = compactQuery({
      page: studentPage.value,
      page_size: studentPageSize,
      q: studentKeyword.value
    });
    const res = await listTeacherStudentsApi(params);
    const normalized = normalizePagedResult(res);
    studentRows.value = normalized.items;
    studentTotal.value = normalized.total;
  } catch (e) {
    studentError.value = e?.response?.data?.detail || '学生列表加载失败';
    studentRows.value = [];
    studentTotal.value = 0;
  } finally {
    studentLoading.value = false;
  }
};

const onFilterChange = async () => {
  currentPage.value = 1;
  await loadApplications();
};

const onPageChange = async (page) => {
  currentPage.value = page;
  await loadApplications();
};

const onStudentFilterChange = async () => {
  studentPage.value = 1;
  await loadStudents();
};

const onStudentPageChange = async (page) => {
  studentPage.value = page;
  await loadStudents();
};

const audit = async (row, action) => {
  if (!row?.id || row.status !== 'pending') return;
  auditLoadingId.value = row.id;
  try {
    const payload = action === 'reject'
      ? { action: 'reject', reject_reason: '当前名额已满' }
      : { action: 'approve' };
    await auditApplicationApi(row.id, payload);
    await Promise.all([loadApplications(), loadStudents()]);
  } finally {
    auditLoadingId.value = 0;
  }
};

const unbindStudent = async (row) => {
  if (!row?.student_id || row.status !== 'bound') return;
  try {
    await ElMessageBox.confirm(
      `确认解绑学生 ${row.student_name || row.username || row.student_id} 吗？解绑后该学生需重新申请。`,
      '解绑确认',
      {
        confirmButtonText: '确认解绑',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );
  } catch (_) {
    return;
  }

  unbindLoadingId.value = row.student_id;
  try {
    await unbindTeacherStudentApi(row.student_id);
    await Promise.all([loadStudents(), loadApplications()]);
  } finally {
    unbindLoadingId.value = 0;
  }
};

onMounted(async () => {
  await Promise.all([loadApplications(), loadStudents()]);
});
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

.toolbar > input,
.toolbar > select {
  flex: 1 1 220px;
  min-width: 0;
}

input,
select {
  height: var(--control-height);
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 0 10px;
  border-radius: var(--control-radius);
}

table {
  width: 100%;
  margin-top: 12px;
  border-collapse: separate;
  border-spacing: 0;
}

th,
td {
  text-align: left;
  padding: 12px 10px;
  border-bottom: 1px solid var(--table-border);
}

th {
  color: var(--ink-muted);
  font-size: 12px;
  font-weight: 600;
  background: color-mix(in oklch, var(--bg-field) 84%, white);
}

tbody tr:hover td {
  background: var(--table-hover-bg);
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.list-panel {
  min-height: 360px;
  display: flex;
  flex-direction: column;
}

.list-panel :deep(.state-shell) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.table-wrap {
  flex: 1;
  overflow: auto;
}

.list-panel :deep(.pager) {
  margin-top: auto;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  font-size: 12px;
}

.status-pending {
  background: rgba(217, 119, 6, 0.12);
  color: #92400e;
  border-color: rgba(217, 119, 6, 0.32);
}

.status-approved {
  background: rgba(22, 163, 74, 0.12);
  color: #166534;
  border-color: rgba(22, 163, 74, 0.3);
}

.status-rejected {
  background: rgba(220, 38, 38, 0.12);
  color: #991b1b;
  border-color: rgba(220, 38, 38, 0.28);
}

button.ghost {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--accent);
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  color: var(--ink-body);
  cursor: pointer;
  border-radius: 999px;
}

button.ghost.danger {
  border-color: var(--danger);
  color: var(--danger);
}

@media (max-width: 1020px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}
</style>

