# cursor-deep-plus

一个基于 FastAPI 的轻量级 LLM 网关服务，用统一的 OpenAI Compatible 接口对接上游模型服务，并记录请求日志到本地 SQLite。

## 功能特性

- 提供 OpenAI 风格接口：`/v1/models`、`/v1/chat/completions`
- 支持普通响应与流式响应（SSE）
- 通过 `MODEL_MAP_JSON` 将公开模型名映射到上游真实模型名
- 使用 Bearer Token 保护网关接口
- 自动记录请求与响应元数据到 SQLite
- 支持通过 `DROP_FIELDS` 删除不希望透传到上游的字段
- 提供 Docker 部署方式
- 提供带窗口的 Windows 桌面壳，便于本地运行和打包为 `.exe`

## 项目结构

```text
.
├─app/
│  ├─api/                  # 路由、鉴权、错误处理
│  ├─desktop/              # 桌面版内嵌 HTML 界面
│  ├─providers/            # 上游模型适配层
│  ├─schemas/              # 请求/响应模型
│  ├─config.py             # 环境变量配置
│  └─main.py               # FastAPI 应用入口
├─services/                # 日志服务
├─storage/                 # SQLite 初始化与数据访问
├─desktop_app.py           # Windows 桌面程序入口
├─build_windows_exe.ps1    # 打包桌面 exe 的脚本
├─.env.example             # 环境变量示例
├─Dockerfile               # 容器镜像构建文件
└─requirements.txt         # Python 依赖
```

## 接口说明

### 1. 健康检查

- 路径：`GET /health`
- 说明：返回服务健康状态
- 鉴权：需要 Bearer Token

示例返回：

```json
{
  "status": "ok"
}
```

### 2. 获取模型列表

- 路径：`GET /v1/models`
- 说明：返回对外暴露的模型列表
- 数据来源：`MODEL_MAP_JSON`
- 鉴权：需要 Bearer Token

### 3. 聊天补全

- 路径：`POST /v1/chat/completions`
- 说明：兼容 OpenAI Chat Completions 请求格式
- 鉴权：需要 Bearer Token
- 支持：普通模式、`stream=true` 流式模式

最小请求示例：

```json
{
  "model": "cursor-proxy",
  "messages": [
    {
      "role": "user",
      "content": "你好"
    }
  ]
}
```

## 环境变量

可参考项目根目录下的 `.env.example`。

| 变量名 | 说明 | 默认值 |
| --- | --- | --- |
| `APP_NAME` | 应用名称 | `cursor-deep-plus` |
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 监听端口 | `8787` |
| `OPENAI_BASE_URL` | 上游 OpenAI Compatible 服务地址 | 空 |
| `OPENAI_API_KEY` | 上游服务 API Key | 空 |
| `OPENAI_MODEL` | 默认上游模型 | `gpt-4o-mini` |
| `PUBLIC_MODEL_NAME` | 默认公开模型名 | `cursor-proxy` |
| `MODEL_MAP_JSON` | 公开模型与上游模型映射 JSON | `{"cursor-proxy":"gpt-4o-mini","cursor-fast":"gpt-4.1-mini"}` |
| `GATEWAY_API_KEY` | 访问当前网关所需 Bearer Token | `local-dev-token` |
| `REQUEST_TIMEOUT_SECONDS` | 上游请求超时秒数 | `600` |
| `LOG_DB_PATH` | SQLite 日志文件路径 | `storage/chat_logs.db` |
| `MAX_LOGGED_BODY_CHARS` | 日志中请求/响应体最大保留字符数 | `12000` |
| `DROP_FIELDS` | 发送到上游前要删除的字段列表，支持逗号分隔或 JSON 数组 | 空 |

## 本地开发

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并按需修改：

```bash
copy .env.example .env
```

至少需要配置：

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `GATEWAY_API_KEY`

### 3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8787 --reload
```

启动后访问：

- 健康检查：`http://127.0.0.1:8787/health`
- 模型列表：`http://127.0.0.1:8787/v1/models`
- 聊天接口：`http://127.0.0.1:8787/v1/chat/completions`
- 桌面版页面：`http://127.0.0.1:8787/desktop`

## Windows 桌面版

### 直接启动带窗口的软件

安装依赖后运行：

```bash
python desktop_app.py
```

这会：

1. 在本地启动 FastAPI 服务
2. 打开一个桌面窗口
3. 在窗口里显示内置管理界面
4. 支持健康检查、模型列表刷新、直接发送聊天测试请求

### 打包为 Windows `.exe`

项目已经提供 PowerShell 打包脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows_exe.ps1
```

打包成功后输出文件位于：

```text
dist/cursor-deep-plus-desktop.exe
```

### 手动打包命令

如果你想自己执行 PyInstaller，也可以使用：

```bash
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --name cursor-deep-plus-desktop --onefile --windowed --collect-submodules webview --add-data "app/desktop/index.html;app/desktop" desktop_app.py
```

## 调用示例

### 获取模型列表

```bash
curl http://127.0.0.1:8787/v1/models ^
  -H "Authorization: Bearer local-dev-token"
```

### 发起聊天请求

```bash
curl http://127.0.0.1:8787/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer local-dev-token" ^
  -d "{\"model\":\"cursor-proxy\",\"messages\":[{\"role\":\"user\",\"content\":\"介绍一下你自己\"}]}"
```

### 流式请求

```bash
curl http://127.0.0.1:8787/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer local-dev-token" ^
  -d "{\"model\":\"cursor-proxy\",\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":\"请分段回答\"}]}"
```

## Docker 运行

### 构建镜像

```bash
docker build -t cursor-deep-plus .
```

### 启动容器

```bash
docker run --rm -p 8787:8787 --env-file .env cursor-deep-plus
```

## 日志说明

服务会在启动时自动初始化 SQLite 数据库，并将聊天请求的关键信息写入 `chat_logs` 表，包括：

- 请求时间
- 请求路径
- 请求模型 / 实际上游模型
- 是否流式
- 上游状态码 / 网关状态码
- 截断后的请求体与响应体
- 错误信息
- 耗时
- 客户端 IP、User-Agent、消息数、用户标识等

适合用于本地调试、调用审计和简单运营分析。

## 错误处理

项目对以下情况做了统一错误响应封装：

- Bearer Token 缺失或错误
- 请求参数校验失败
- 上游超时
- 上游 HTTP 请求失败
- 上游返回非法 JSON
- 其他未处理异常

错误格式统一为：

```json
{
  "error": {
    "message": "错误说明",
    "type": "gateway_error"
  }
}
```

## 适用场景

- 为现有上游模型服务增加统一入口
- 给客户端暴露更稳定的模型命名
- 本地搭建简单的 LLM 代理层
- 为模型调用增加基础日志能力
- 作为可分发的 Windows 桌面工具使用

## 许可证

如需开源发布，请按你的实际需求补充许可证信息。
