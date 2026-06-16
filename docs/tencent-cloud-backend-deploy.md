# 腾讯云轻量服务器部署后端

目标：把 Django 后端部署到腾讯云轻量服务器，并让 GitHub Pages 前端访问公网后端。

> 重要：GitHub Pages 是 HTTPS 页面，后端也必须使用 HTTPS。不要只暴露 `http://服务器IP:8000`，否则浏览器会拦截 API 请求。

## 1. 购买和初始化服务器

推荐配置：

- 系统：Ubuntu 22.04 LTS
- 配置：2 核 2G 起步；如果 AI/PDF 功能使用频繁，建议 2 核 4G
- 防火墙放行：`22`、`80`、`443`

建议准备一个域名，例如：

```text
api.example.com
```

把域名 DNS 的 `A` 记录解析到轻量服务器公网 IP。没有域名时可以先用 IP 测试后端，但最终接 GitHub Pages 前端时建议配置 HTTPS 域名。

## 2. 登录服务器并安装系统依赖

```bash
ssh ubuntu@你的服务器IP
```

安装基础依赖：

```bash
sudo apt update
sudo apt install -y software-properties-common curl git nginx redis-server build-essential libgl1 libglib2.0-0
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

启动 Redis：

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

## 3. 拉取代码

```bash
cd /opt
sudo git clone https://github.com/cxtdylove-1747/-alpha.git innovation-agent
sudo chown -R ubuntu:ubuntu /opt/innovation-agent
cd /opt/innovation-agent/backend
```

如果仓库是私有仓库，需要先在 GitHub 配置访问权限，或使用 HTTPS token/SSH key 拉取。

## 4. 创建 Python 环境并安装依赖

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. 配置后端环境变量

创建 `/opt/innovation-agent/backend/.env`：

```bash
nano /opt/innovation-agent/backend/.env
```

写入以下内容，并按实际情况修改：

```env
DEBUG=False
SECRET_KEY=请换成很长的随机字符串
ALLOWED_HOSTS=api.example.com,你的服务器IP
CORS_ALLOWED_ORIGINS=https://cxtdylove-1747.github.io

DB_ENGINE=django.db.backends.sqlite3

REDIS_URL=redis://127.0.0.1:6379/1

OPENAI_API_KEY=你的AI接口Key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

生成 `SECRET_KEY` 可以用：

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

说明：

- 上面使用 SQLite，适合课程展示和轻量演示。
- 如果多人长期使用，建议后续换 MySQL/PostgreSQL。
- `CORS_ALLOWED_ORIGINS` 只需要写 GitHub Pages 的源，不带路径，所以是 `https://cxtdylove-1747.github.io`。

## 6. 初始化数据库和静态文件

```bash
cd /opt/innovation-agent/backend
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_demo
```

检查后端：

```bash
python manage.py check
```

## 7. 配置 Gunicorn systemd 服务

创建服务文件：

```bash
sudo nano /etc/systemd/system/innovation-agent.service
```

写入：

```ini
[Unit]
Description=Innovation Agent Django backend
After=network.target redis-server.service

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/opt/innovation-agent/backend
EnvironmentFile=/opt/innovation-agent/backend/.env
ExecStart=/opt/innovation-agent/backend/.venv/bin/python -m gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 2 --timeout 300
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable innovation-agent
sudo systemctl start innovation-agent
sudo systemctl status innovation-agent
```

查看日志：

```bash
journalctl -u innovation-agent -f
```

## 8. 配置 Nginx 反向代理

创建配置：

```bash
sudo nano /etc/nginx/sites-available/innovation-agent
```

写入，先把 `api.example.com` 改成你的域名：

```nginx
server {
    listen 80;
    server_name api.example.com;

    client_max_body_size 50m;

    location /static/ {
        alias /opt/innovation-agent/backend/staticfiles/;
    }

    location /media/ {
        alias /opt/innovation-agent/backend/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/innovation-agent /etc/nginx/sites-enabled/innovation-agent
sudo nginx -t
sudo systemctl reload nginx
```

现在可以先测试：

```text
http://api.example.com/api/health/
```

## 9. 配置 HTTPS

安装 Certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
```

申请证书：

```bash
sudo certbot --nginx -d api.example.com
```

证书成功后，测试：

```text
https://api.example.com/api/health/
```

## 10. 让 GitHub Pages 前端连接腾讯云后端

打开 GitHub 仓库：

```text
Settings -> Secrets and variables -> Actions -> Variables
```

新增或修改变量：

```text
VITE_BACKEND_ORIGIN=https://api.example.com
```

然后到：

```text
Actions -> Deploy frontend to GitHub Pages -> Run workflow
```

重新部署前端。

最终用户访问：

```text
https://cxtdylove-1747.github.io/-alpha/
```

前端会调用：

```text
https://api.example.com/api/
```

## 11. 后续更新代码

服务器上更新后端：

```bash
cd /opt/innovation-agent
git pull
cd backend
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart innovation-agent
```

## 12. 常见问题

### 前端请求失败

检查：

- GitHub Actions 变量 `VITE_BACKEND_ORIGIN` 是否是 HTTPS 后端域名
- 后端 `.env` 的 `CORS_ALLOWED_ORIGINS` 是否包含 `https://cxtdylove-1747.github.io`
- 后端 `.env` 的 `ALLOWED_HOSTS` 是否包含后端域名
- 腾讯云防火墙是否放行 `80` 和 `443`

### 登录失败或接口 500

看后端日志：

```bash
journalctl -u innovation-agent -n 100 --no-pager
```

### 上传 PDF 失败

检查：

- Nginx 是否设置了 `client_max_body_size 50m`
- `backend/media/` 是否存在并且服务用户可写

```bash
mkdir -p /opt/innovation-agent/backend/media
sudo chown -R ubuntu:www-data /opt/innovation-agent/backend/media
```
