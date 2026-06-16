# Frontend Redesign (V2 Reborn)

## Current Scope
- Rebuilt the frontend shell, login, and role workspaces from scratch in Vue 3.
- Kept API contracts and route paths stable for backend compatibility.
- Replaced section-driven shared pages with independent student/teacher module pages.

## New Architecture
- App shell: `src/components/core/AppShell.vue`
- Public entry: `src/pages/reborn/LoginPortal.vue`
- Student pages: `src/pages/reborn/student/*`
- Teacher pages: `src/pages/reborn/teacher/*`
- Admin page: `src/pages/reborn/AdminNexus.vue`
- Route mapping: `src/router/index.js`

## Design System
- Theme tokens: `src/styles/theme.css`
- CSS reset: `src/styles/reset.css`
- Neutral warm palette with strong ink contrast and semantic accent usage.
- No legacy card gradient language, no legacy nav patterns.

## Independent Module Routes
- Student: `/student/home`, `/student/plan`, `/student/review`, `/student/competition`, `/student/knowledge`, `/student/mentor`, `/student/profile`
- Teacher: `/teacher/home`, `/teacher/analytics`, `/teacher/students`, `/teacher/reviews`, `/teacher/prep`
- Admin: `/admin/console`

## Runtime Notes
- Request errors are emitted via `window` event (`app:notify`) and rendered by app-level toast stack.
- Auth flow and role guards remain in `src/router/index.js` + `src/stores/auth.js`.

## Integration Enhancement (Option 3)
- Added reusable async state block: `src/components/core/AsyncState.vue`.
- Added reusable pager: `src/components/core/SimplePager.vue`.
- Added list helpers (`asArray`, `paginate`): `src/composables/list.js`.
- Enhanced pages with loading/empty/error + retry + filters + pagination:
  - `src/pages/reborn/student/StudentPlan.vue`
  - `src/pages/reborn/student/StudentReview.vue`
  - `src/pages/reborn/student/StudentMentor.vue`
  - `src/pages/reborn/teacher/TeacherStudents.vue`
  - `src/pages/reborn/teacher/TeacherReviews.vue`
- Rolled out to remaining routed pages for consistency:
  - `src/pages/reborn/student/StudentHome.vue`
  - `src/pages/reborn/student/StudentCompetition.vue`
  - `src/pages/reborn/student/StudentKnowledge.vue`
  - `src/pages/reborn/student/StudentProfile.vue`
  - `src/pages/reborn/teacher/TeacherHome.vue`
  - `src/pages/reborn/teacher/TeacherAnalytics.vue`
  - `src/pages/reborn/teacher/TeacherPrep.vue`
  - `src/pages/reborn/AdminNexus.vue`
- Current pagination is frontend-side slicing for quick rollout; can switch to backend pagination params later without UI rewrite.

## Backend Pagination Migration (Completed)
- Added shared helpers for parameterized list requests:
  - `compactQuery` and `normalizePagedResult` in `src/composables/list.js`
- Updated API methods to accept `page/page_size/q/status` params:
  - `src/api/student.js`: `listPlansApi`, `listPlanReviewsApi`, `listMentorApplicationsApi`, `listMessagesApi`, `historyApi`
  - `src/api/teacher.js`: `listApplicationsApi`, `highRiskProjectsApi`, `commonIssuesApi`, `promptScenesApi`, `listPlansApi`, `listPlanReviewsApi`
- Migrated major list pages to backend-parameter-driven mode (with local fallback if backend returns non-paged arrays):
  - `src/pages/reborn/student/StudentPlan.vue`
  - `src/pages/reborn/student/StudentReview.vue`
  - `src/pages/reborn/student/StudentMentor.vue`
  - `src/pages/reborn/student/StudentProfile.vue`
  - `src/pages/reborn/teacher/TeacherStudents.vue`
  - `src/pages/reborn/teacher/TeacherReviews.vue`
  - `src/pages/reborn/teacher/TeacherHome.vue`
  - `src/pages/reborn/teacher/TeacherPrep.vue`
- Completed remaining board-aggregation pages with independent paged sources:
  - `src/pages/reborn/student/StudentHome.vue`
    - three independent streams: plans (`/plans`), messages (`/messages`), history (`/history?mode=stream`)
  - `src/pages/reborn/teacher/TeacherAnalytics.vue`
    - indicator stream endpoint: `/teacher/metrics-stream`

