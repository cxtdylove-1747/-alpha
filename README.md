# 创新创业智能体平台

这是一个前后端分离项目：

- `frontend/`: Vue 3 + Vite + Pinia + Vue Router + Element Plus + ECharts
- `backend/`: Django + DRF + JWT

GitHub Pages 只能托管静态网页，因此本仓库的 Pages 工作流只发布 `frontend/dist`。登录、AI 对话、上传、评审等接口功能仍需要一个公网可访问的后端服务。

## 必要目录

```text
frontend/              前端源码与构建配置
backend/               后端源码、接口和数据库迁移
docs/                  项目说明与接口文档
.github/workflows/     GitHub Pages 自动部署
```

本地依赖、数据库、上传媒体、构建产物、课程提交材料、压缩包和重复源码目录不会提交到 Git。

## 本地运行

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## GitHub Pages 发布

仓库推送到 GitHub 后，进入 `Settings -> Pages`，将 `Build and deployment` 的来源设为 `GitHub Actions`。

如果前端需要连接公网后端，在 GitHub 仓库里设置变量：

- `Settings -> Secrets and variables -> Actions -> Variables`
- 新增 `VITE_BACKEND_ORIGIN`，值为后端域名，例如 `https://api.example.com`
- 可选新增 `VITE_API_BASE`，通常不需要；默认会使用 `${VITE_BACKEND_ORIGIN}/api`

之后每次推送到 `main` 分支都会自动构建并发布前端页面。
