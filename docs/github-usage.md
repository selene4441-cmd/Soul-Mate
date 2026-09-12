# 在 GitHub 中使用同频

## 方式一：GitHub Codespaces

打开仓库页面后，点击 README 中的 **Open in GitHub Codespaces**，也可以直接访问：

```text
https://codespaces.new/selene4441-cmd/Soul-Mate
```

环境创建完成后会执行：

1. 安装 Python 3.12 和 Node.js 22。
2. 创建 `.venv` 并安装后端依赖。
3. 执行 Alembic 迁移，创建本地 SQLite 数据库。
4. 安装 pnpm 依赖。
5. 启动 FastAPI：`127.0.0.1:8000`。
6. 启动 Next.js：`0.0.0.0:3000`。

在编辑器的 **Ports** 面板打开 `3000`，或点击 `openPreview` 提示即可使用。

Codespaces 的数据是隔离的。每一个同伴打开自己的 Codespace 后，都会得到一份新的种子数据，不会连接到你正在运行的数据库。

## 方式二：Docker Compose

需要共享 PostgreSQL、Redis 和同一套数据时，可在支持 Docker 的云主机或本地运行：

```bash
docker compose -f infra/compose/docker-compose.yml up --build
```

然后访问 `http://服务器地址:3000`。生产环境还需要配置 HTTPS、域名、密钥管理、WAF 和备份；不要直接暴露当前开发配置。

## 方式三：本地克隆

```bash
git clone https://github.com/selene4441-cmd/Soul-Mate.git
cd Soul-Mate
bash scripts/start-local.sh
```

Windows PowerShell：

```powershell
git clone https://github.com/selene4441-cmd/Soul-Mate.git
cd Soul-Mate
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

## 为什么不能直接用 GitHub Pages

GitHub Pages 只能托管静态文件，不能运行 FastAPI、WebSocket、PostgreSQL 或 Cookie 会话。Web 前端通过 `/api/v1` 同源代理访问后端，因此需要 Codespaces、Docker Compose 或云服务这样的可运行环境。

## 推送到 GitHub

Codespaces 链接只会在对应提交已经推送到 GitHub 后包含最新代码。确认测试通过后执行：

```bash
git push origin main
```

如果仓库属于组织或开启了分支保护，请先创建 Pull Request，等 CI 通过后合并。