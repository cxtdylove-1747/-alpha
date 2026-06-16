# 部署说明

## 1. 环境依赖

- Python 3.11+
- Node.js 18+
- MySQL 8+
- Redis 6+
- 可选 OCR（扫描版PDF）：Tesseract OCR

## 2. 后端部署（Django）

```powershell
cd C:\Users\Admin\PycharmProjects\智能体\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py import_case_library --data-root ..\data
python manage.py collectstatic --noinput
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

生产环境建议：
- 使用 `gunicorn` 或 `uvicorn` + `nginx`
- `DEBUG=False`
- 配置 HTTPS 与反向代理
- 使用 MySQL/Redis 独立服务

## 3. 前端部署（Vue3）

```powershell
cd C:\Users\Admin\PycharmProjects\智能体\frontend
npm install
npm run build
npm run preview
```

打包后产物：`frontend/dist/`

## 4. 前后端对接配置

- 开发期通过 `vite.config.js` 代理 `/api -> 8000`
- 生产期请在 nginx 做反向代理：
  - `/` -> 前端静态资源
  - `/api/` -> Django服务

## 5. Redis与MySQL

- 创建数据库：执行 `backend/scripts/mysql_init.sql`
- Redis默认：`redis://127.0.0.1:6379/1`
- `.env` 中可调整连接信息

## 5.1 OCR可选配置

- 当前默认使用 `pypdf` 提取文本。
- 若上传为扫描版PDF，可在 `backend/apps/core/ocr_utils.py` 中接入OCR实现（如 `pytesseract`）。

## 6. 核心测试用例

1. 学生登录后在 `智能引导` 提交回答，确认返回下一轮提问。
2. 学生上传PDF，在 `方案管理` 生成学生端批阅（只含引导问题）。
3. 学生提交师徒申请，教师端 `学生管理` 审核通过。
4. 学生提交方案给已绑定教师，教师在 `方案批阅` 生成建议。
5. 教师在 `可视化看板` 和 `备课辅助` 查看统计与推荐数据。

## 7. 回归清单（本次更新）

1. 学生端-智能体沟通：返回包含 `question/knowledge/example/case_pattern`，且为引导式问题。
2. 学生端-PDF检阅：返回 `annotations + guidance_questions + summary`，并可在PDF标注组件渲染。
3. 教师端-备课辅助：`/teacher/common-issues`、`/teacher/knowledge-recommendations`、`/teacher/ai-chat` 全部可调用。
4. 教师端-评分面板：`/teacher/dashboard`、`/teacher/rubrics`、`/teacher/prompt-scenes`、`/teacher/case-library-summary` 可正常返回。
5. 权限检查：学生不可查看他人方案，教师仅可访问绑定学生方案。

## 8. 一键执行顺序（全部继续）

先设置部署环境变量（PowerShell 会话内）：

```powershell
$env:DEPLOY_HOST="121.14.82.109"
$env:DEPLOY_USER="group17"
$env:DEPLOY_PASSWORD="<your-password>"
$env:DEPLOY_BASE_DIR="/home/inspur/datastore/student_groups/group17"
$env:BACKEND_PORT="8171"
$env:FRONTEND_PORT="8170"
```

本地校验：

```powershell
Push-Location "C:\Users\Admin\PycharmProjects\智能体\backend"
python manage.py check
python manage.py test apps.core.tests -v 1
python scripts/smoke_test.py
Pop-Location

Push-Location "C:\Users\Admin\PycharmProjects\智能体\frontend"
npm run build
Pop-Location
```

远端探测与全量部署：

```powershell
Push-Location "C:\Users\Admin\PycharmProjects\智能体"
python scripts/remote_probe.py
python scripts/deploy_group17.py
Pop-Location
```

专项验收：

```powershell
Push-Location "C:\Users\Admin\PycharmProjects\智能体"
python scripts/check_remote_status.py
python scripts/check_remote_pdf_config.py
python scripts/verify_remote_dist_strings.py
python scripts/verify_remote_media_pdf.py
Pop-Location
```

通过判据：

- `GET /api/health/` 返回 `status=ok`。
- `GET /api/agent/case-recall` 返回 `retrieval_mode` 字段。
- `GET /api/agent/workflow-orchestrate` 返回 `workflow` 字段。
- 前端能访问 `竞赛辅导`、`学习Tutor`、`学情分析` 页面。
- 教师干预、证据链、潜力报告、班级学情报告接口均可返回数据。


