# 小红书客户数据采集（xhs-collector）

把客户在微信群聊里分享的小红书账号收集起来，调用 TikHub API 拉取公开资料，并存入数据库（默认 SQLite）。自带一个可直接使用的 Web 页面，粘贴即采集，支持导出 CSV。

## 它能做什么

- 粘贴微信群里的分享文案/主页链接/短链/24 位 hex user_id，自动识别并采集
- 通过 TikHub 小红书 App V2 接口 `get_user_info` 拉取：昵称、头像、简介、性别、地区、粉丝、关注、笔记、互动数
- 数据持久化到 SQLite（SQLAlchemy ORM），重复采集自动更新、不产生重复记录
- 纯“小红书号”（例如 `757954382`）无法被 TikHub 直接解析，会进入“待解析”，可补主页链接后一键解析
- 提供 Web UI、REST API、CSV 导出

## 目录

```text
services/xhs-collector/
  app/
    config.py        配置（TIKHUB_API_KEY 等）
    database.py      SQLAlchemy engine/session
    models.py        XhsUser 数据表
    normalize.py     账号文本识别（链接/短链/uid/小红书号）
    tikhub.py        TikHub 客户端 + 响应解析
    service.py       采集编排、去重、入库
    schemas.py       API 数据模型
    routes.py        REST API
    factory.py       create_app 工厂
    main.py          uvicorn 入口
    static/          单页 Web UI
  tests/             单元 + API 测试
```

## 快速开始

1. 准备 Python 3.12 环境和依赖（本仓库根目录的 `.python312` 已内置依赖）：

```powershell
cd services/xhs-collector
Copy-Item .env.example .env
# 编辑 .env，填入 TIKHUB_API_KEY
```

2. 启动服务：

```powershell
..\..\.python312\python.exe run.py
```

3. 打开 http://127.0.0.1:8000 ，把客户在群里分享的账号整段粘贴进去，点“开始采集”。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/collect` | 批量采集，body `{"text": "..."}` |
| GET | `/api/v1/leads` | 列表，支持 `status`、`q`、`limit`、`offset` |
| GET | `/api/v1/leads/{id}` | 单条记录 |
| POST | `/api/v1/leads/{id}/resolve` | 给“待解析”记录补 `user_id`/`share_text` |
| GET | `/api/v1/leads/export.csv` | 导出 CSV |

## 支持的账号输入格式

| 输入 | 示例 | 处理方式 |
|---|---|---|
| 主页链接 | `https://www.xiaohongshu.com/user/profile/61b46d790000000010008153` | 提取 user_id 后采集 |
| 分享短链 | `http://xhslink.com/a/xxxx` | 以 share_text 交给 TikHub 解析 |
| 24 位 hex user_id | `61b46d790000000010008153` | 直接采集 |
| 小红书号 | `757954382` | 进入“待解析”，需补主页链接 |

## 测试

```powershell
..\..\.python312\python.exe -m pytest tests -q
```

测试使用内存 SQLite 和 Fake TikHub 客户端，不产生真实网络请求。

## 合规提醒

- 抖音/小红书/微信官方均不开放此类批量拉取能力，TikHub 是第三方接口，存在接口失效、账号风控风险。
- 采集个人信息需取得客户同意，请遵守《个人信息保护法》(PIPL) 及平台规则。
- 本工具只处理客户主动提供的公开资料，请勿用于爬取微信群成员列表等越权行为。