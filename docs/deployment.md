# Mini Claw Platform — 部署与运维手册

## 目录

- [架构概览](#架构概览)
- [环境信息](#环境信息)
- [自动部署 (CI/CD)](#自动部署-cicd)
- [手动部署](#手动部署)
- [服务器检查](#服务器检查)
- [常用运维命令](#常用运维命令)
- [故障排查](#故障排查)

---

## 架构概览

```
┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │
│  Next.js     │     │  FastAPI     │
│  :3002       │     │  :8001       │
└──────────────┘     └──────┬───────┘
                            │
                  ┌─────────┼─────────┐
                  ▼                   ▼
           ┌────────────┐     ┌────────────┐
           │ PostgreSQL │     │   Redis    │
           │ pgvector   │     │            │
           │ :5433      │     │ internal   │
           └────────────┘     └────────────┘
```

所有服务通过 `docker-compose.prod.yml` 编排，运行在同一台服务器上。

## 环境信息

| 项目 | 值 |
|------|------|
| QA 服务器 | `47.236.110.51` |
| SSH Key | `aigc.pem` |
| SSH 用户 | `root` |
| 项目目录 | `/opt/mini_claw` |
| GitHub Repo | `https://github.com/guyil/mini_claw` |
| 分支 | `main` |

### 端口分配

| 服务 | 容器内端口 | 外部端口 |
|------|-----------|---------|
| Frontend (Next.js) | 3000 | **3002** |
| Backend (FastAPI) | 8000 | **8001** |
| PostgreSQL | 5432 | **5433** |
| Redis | 6379 | 内部网络 |

### 访问地址

- 前端: `http://47.236.110.51:3002`
- 后端 API: `http://47.236.110.51:8001`
- 健康检查: `http://47.236.110.51:8001/health`

---

## 自动部署 (CI/CD)

### 工作流程

每次 push 到 `main` 分支，GitHub Actions 会自动:

1. SSH 到 QA 服务器
2. `git pull` 最新代码
3. `docker compose build --no-cache` 重新构建镜像
4. `docker compose up -d` 滚动更新服务
5. 健康检查确认部署成功

### 配置文件

- 工作流定义: `.github/workflows/deploy-qa.yml`
- GitHub Secret: `QA_SSH_KEY` (存储 `aigc.pem` 私钥内容)

### 如何更新 SSH Key

```bash
# 本地执行
gh secret set QA_SSH_KEY --repo guyil/mini_claw < /path/to/aigc.pem
```

### 查看部署状态

```bash
# 查看最近的 Actions 运行
gh run list --repo guyil/mini_claw --limit 5

# 查看某次运行的日志
gh run view <run-id> --repo guyil/mini_claw --log
```

---

## 手动部署

### 首次部署

```bash
# 1. SSH 到服务器
ssh -i aigc.pem root@47.236.110.51

# 2. 安装 git (如果没有)
yum install -y git

# 3. 克隆项目
git clone -b main https://github.com/guyil/mini_claw.git /opt/mini_claw

# 4. 配置环境变量
cd /opt/mini_claw
cp .env.example .env
vi .env   # 填写生产配置

# 5. 构建并启动
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

### 更新部署

```bash
ssh -i aigc.pem root@47.236.110.51

cd /opt/mini_claw
git fetch origin main
git reset --hard origin/main
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

### 使用部署脚本

```bash
# 在服务器上执行
bash /opt/mini_claw/scripts/deploy.sh
```

---

## 服务器检查

### 快速健康检查

```bash
# 从本地检查
curl http://47.236.110.51:8001/health
# 期望输出: {"status":"ok"}

# 检查前端
curl -s -o /dev/null -w "%{http_code}" http://47.236.110.51:3002
# 期望输出: 200
```

### SSH 登录检查

```bash
ssh -i aigc.pem root@47.236.110.51
```

### 容器状态检查

```bash
# 查看所有 mini_claw 容器状态
docker compose -f /opt/mini_claw/docker-compose.prod.yml ps

# 期望看到 4 个容器 (postgres, redis, backend, frontend) 状态为 Up
```

### 资源使用情况

```bash
# 磁盘
df -h /

# 内存
free -h

# CPU & 容器资源
docker stats --no-stream

# Docker 磁盘占用
docker system df
```

### 数据库连接检查

```bash
# 从服务器本地检查
docker exec mclaw_postgres pg_isready -U mclaw
# 期望输出: accepting connections

# 进入数据库
docker exec -it mclaw_postgres psql -U mclaw -d mclaw -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
```

### 日志检查

```bash
# 查看所有服务日志
docker compose -f /opt/mini_claw/docker-compose.prod.yml logs --tail=50

# 只看后端日志
docker compose -f /opt/mini_claw/docker-compose.prod.yml logs --tail=100 backend

# 实时跟踪日志
docker compose -f /opt/mini_claw/docker-compose.prod.yml logs -f backend
```

---

## 常用运维命令

### 重启服务

```bash
cd /opt/mini_claw

# 重启所有服务
docker compose -f docker-compose.prod.yml restart

# 只重启后端
docker compose -f docker-compose.prod.yml restart backend

# 只重启前端
docker compose -f docker-compose.prod.yml restart frontend
```

### 停止 / 启动

```bash
# 停止所有服务 (保留数据)
docker compose -f docker-compose.prod.yml down

# 停止并删除数据卷 (⚠️ 会丢失数据库数据)
docker compose -f docker-compose.prod.yml down -v

# 启动
docker compose -f docker-compose.prod.yml up -d
```

### 数据库迁移

```bash
# 在后端容器中执行 Alembic 迁移 (启动时会自动执行)
docker exec mclaw_backend alembic upgrade head
```

### 清理 Docker 缓存

```bash
# 清理悬空镜像
docker image prune -f

# 深度清理 (未使用的镜像、网络、缓存)
docker system prune -af
```

---

## 故障排查

### 后端启动失败

```bash
# 1. 查看后端日志
docker compose -f docker-compose.prod.yml logs backend

# 2. 常见原因:
#    - 数据库连接失败 → 检查 postgres 容器是否健康
#    - .env 配置错误 → 检查 DATABASE_URL 格式
#    - 端口冲突 → 检查 8001 是否被占用
lsof -i :8001
```

### 前端无法访问后端

```bash
# 1. 确认后端容器在运行
docker compose -f docker-compose.prod.yml ps backend

# 2. 从前端容器内测试连通性
docker exec mclaw_frontend wget -q -O- http://backend:8000/health

# 3. 检查 Docker 网络
docker network ls | grep mini_claw
```

### 数据库迁移失败

```bash
# 1. 查看迁移状态
docker exec mclaw_backend alembic current

# 2. 查看历史
docker exec mclaw_backend alembic history

# 3. 手动重试
docker exec mclaw_backend alembic upgrade head
```

### 磁盘空间不足

```bash
# 清理 Docker
docker system prune -af
docker volume prune -f

# 查看大文件
du -sh /var/lib/docker/
```
