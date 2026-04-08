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
- 已内置应用图标、打包脚本和安装包脚本

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
├─assets/                  # 图标资源
├─services/                # 日志服务
├─storage/                 # SQLite 初始化与数据访问
├─desktop_app.py           # Windows 桌面程序入口
├─build_windows_exe.ps1    # 打包桌面 exe 的脚本
├─build_installer.ps1      # 打包安装程序脚本
├─installer.iss            # Inno Setup 安装脚本
├─.env.example             # 环境变量示例
├─Dockerfile               # 容器镜像构建文件
└─requirements.txt         # Python 依赖
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

### 4. 启动桌面版

```bash
python desktop_app.py
```

## Windows 桌面打包

### 生成单文件 exe

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows_exe.ps1
```

输出：

```text
dist/cursor-deep-plus-desktop.exe
```

### 生成安装包

先安装 Inno Setup 6，然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

输出：

```text
installer-dist/cursor-deep-plus-desktop-setup.exe
```

### 手动打包命令

```bash
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --name cursor-deep-plus-desktop --onefile --windowed --icon "assets/app.ico" --collect-submodules webview --add-data "app/desktop/index.html;app/desktop" --add-data "assets/app.ico;assets" desktop_app.py
```

## 说明

- 单文件 exe 已包含桌面页面资源和应用图标。
- 安装包会创建开始菜单快捷方式，并可选创建桌面快捷方式。
- 若未配置 `.env` 中的上游参数，桌面程序可以启动，但聊天请求不会成功。
- 若未安装 Inno Setup，则只能先生成 exe，不能生成安装包。
