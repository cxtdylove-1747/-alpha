# 创新创业多智能体平台自测试报告（2026-04-27）

## 1. 测试目标
- 基于当前代码仓目录，对前后端核心可执行自测项进行一次端到端自检。
- 输出可复现的命令结果、失败项定位与修复建议。

## 2. 测试环境
- 执行时间：2026-04-27 00:26:15 +08:00
- 操作系统：Windows（PowerShell）
- Python：3.11.0
- Node.js：v24.14.0
- npm：11.9.0

## 3. 项目规模快照（源代码盘点）
- 后端：Django + DRF（`backend/requirements.txt`）
- 前端：Vue3 + Vite + Element Plus（`frontend/package.json`）
- 后端 API 路由数：71（`backend/apps/core/urls.py` 中 `path(...)` 统计）
- 后端 Python 文件数：55（`backend/apps`，不含 `migrations`）
- 前端 Vue 文件数：26（`frontend/src/**/*.vue`）
- 后端测试入口文件：
  - `backend/apps/core/tests.py`
  - `backend/apps/core/tests_hypergraph_client.py`
  - `backend/scripts/smoke_test.py`

## 4. 执行项与结果
| 序号 | 自测项 | 命令 | 结果 |
|---|---|---|---|
| 1 | Django 系统检查 | `python manage.py check` | 通过 |
| 2 | 后端单元测试 | `python manage.py test` | 失败（23 项中 2 项异常） |
| 3 | 冒烟测试 | `python scripts/smoke_test.py` | 通过（输出 `smoke_test passed`） |
| 4 | Python 语法编译检查 | `python -m compileall apps config scripts` | 通过 |
| 5 | 前端 Lint（npm script） | `npm.cmd run lint` | 失败（脚本环境未正确拉起 `eslint`） |
| 6 | 前端 Build（npm script） | `npm.cmd run build` | 失败（脚本环境未正确拉起 `vite`） |
| 7 | 前端 Lint（直接调用 bin） | `.\\node_modules\\.bin\\eslint.cmd . --ext .js,.vue` | 失败（ESM/CJS 配置冲突） |
| 8 | 前端构建（直接调用 bin） | `.\\node_modules\\.bin\\vite.cmd build` | 通过（有大包告警） |

## 5. 失败项定位

### A. 后端测试报错：`NameError`
- 失败用例：`test_compact_hypergraph_context_contains_new_fields`
- 现象：`_compact_hypergraph_context` 未定义
- 位置：
  - `backend/apps/core/tests_hypergraph_client.py:162`
  - 当前文件仅导入 `build_plan_diagnosis/build_plan_rubric_basis`，未导入 `_compact_hypergraph_context`
  - 该函数定义存在于 `backend/apps/core/ai_engine.py:567`
- 影响：阻断该测试用例，降低 CI 稳定性。

### B. 后端权限测试失败：预期 403 实际 201
- 失败用例：`test_teacher_intervention_permissions`
- 现象：非绑定教师可成功创建干预（201）
- 位置：
  - 断言失败：`backend/apps/core/tests.py:87`
  - 接口逻辑：`backend/apps/core/views.py:3969`
  - 权限计算函数：`backend/apps/core/views.py:1532-1564`
- 根因：`TeacherInterventionCreateView` 调用 `_teacher_can_access_plan(..., allow_plan_fallback=True)`，当教师无绑定学生时会回退到“全部已提交计划学生”，导致权限放宽。
- 影响：教师干预接口存在越权风险（中高优先级）。

### C. 前端 Lint 配置冲突
- 现象：`frontend/.eslintrc.js` 使用 `module.exports`，但项目 `package.json` 为 `"type": "module"`，Node 将该文件按 ESM 解释，导致 `module is not defined`。
- 位置：
  - `frontend/.eslintrc.js`
  - `frontend/package.json`（`"type": "module"`）
- 影响：Lint 无法运行，影响代码规范门禁。

### D. 前端构建体积告警
- 现象：`vite build` 提示存在大于 500KB 的 chunk，主包约 2.4MB（gzip 约 791KB）。
- 影响：首屏加载与弱网体验存在性能风险（中优先级优化项）。

## 6. 综合结论
- 本轮自测总体结论：**部分通过，暂不建议直接作为“全量通过”发布基线**。
- 关键阻塞：
  - 后端测试未全绿（1 fail + 1 error）。
  - 前端 Lint 未打通。
- 可发布参考：
  - 后端基础运行与冒烟链路可用。
  - 前端可成功构建产物，但需处理规范与性能问题。

## 7. 修复建议（按优先级）
1. 修复教师干预越权：将干预接口中的 `allow_plan_fallback` 调整为 `False`，并补充回归测试。
2. 修复超图测试导入：在 `tests_hypergraph_client.py` 显式导入 `_compact_hypergraph_context`（或改为公共模块导出后引用）。
3. 修复 ESLint 配置：将 `.eslintrc.js` 改名为 `.eslintrc.cjs`，或改为 ESM 格式 `export default`。
4. 前端性能治理：按路由/功能拆包（`dynamic import` + `manualChunks`），降低主包体积。

