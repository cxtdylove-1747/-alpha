# Frontend Interaction Checklist

This checklist verifies the two final closure goals:

1. Project grouping in plan management prioritizes `project_id` and merges versions into a single row.
2. Core interaction flows (chat, upload, mentor apply, paging) work end-to-end with backend APIs.

## A. Plan Grouping and Versioning

- [ ] Open `"/student/plan"` and confirm each logical project appears as one row.
- [ ] Confirm grouping key priority: `project_id` > `project_key` > fallback keys.
- [ ] Confirm version selector (`Vx`) is visible in each row.
- [ ] Switch to an older version and confirm preview and actions target that version.
- [ ] Confirm plan title is single-line truncation with ellipsis and full name on hover tooltip.

## B. Agent Chat Input and Response

- [ ] On `"/student/home"`, type into guide chat textarea and send with Enter.
- [ ] On `"/student/home"`, send with button click and verify response renders.
- [ ] On `"/student/pitch"`, type and send in pitch optimizer chat.
- [ ] On `"/student/competition"`, type and send in competition coach chat.
- [ ] Verify each request reaches API and returns without frontend input lock.

## C. Mentor Interaction

- [ ] Open `"/student/mentor"` and search by teacher name.
- [ ] Confirm each mentor card shows name, major, contact placeholder.
- [ ] Click "提交申请" and verify confirmation panel appears.
- [ ] Submit with required fields and verify record appears in application history.

## D. Paging and Non-jumping UX

- [ ] In `"/student/profile"` recent activity, switch pages and verify card height remains stable.
- [ ] Confirm no full loading placeholder flash during page switch.
- [ ] Verify `AsyncState` keeps minimum shell height in list panels.

## E. Routing and Page Split

- [ ] Confirm student nav has `"路演优化"` and `"竞赛辅导"` as separate pages.
- [ ] Confirm `"/student/review"` redirects to `"/student/plan"`.
- [ ] Confirm `"/student/pitch"` and `"/student/competition"` are independently reachable.

## F. Visual Consistency

- [ ] File input trigger button style matches global button family.
- [ ] Font rendering is consistent across student pages (body + heading).
- [ ] Operation buttons in plan table are on one row with compact size.

