# L1 异地开发指南

本仓库属于 [CodePick 四层平台](https://github.com/jayson2hu/codepick-docs)。建议四个代码仓库保持同级目录，以便查阅关联实现；每个项目使用独立虚拟环境。

## 克隆与环境

需要 Git 和 Python 3.11 或更新版本。以下命令都从本仓库根目录执行。

```sh
git clone https://github.com/jayson2hu/seek_data.git
cd seek_data
python -m venv .venv
```

激活环境：Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`；macOS/Linux 使用 `source .venv/bin/activate`。随后执行：

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m l1_data_processing.smoke
python -m l1_data_processing.dod
```

## 当前运行模式

当前默认使用 StubContentProvider、FakeLLM 和内存存储。接入真实 L0、模型、数据库及事件总线仍属于后续集成工作；交接不代表全平台已完成真实联调。

## 交接范围

提交包括当前源码、测试、迁移、配置示例与项目文档。依赖目录、构建产物、本地数据库、采集运行数据、日志和凭据不随仓库分发，需要在新环境重新安装或配置。

各层状态与验收证据见项目 README 和 docs；本文提供恢复开发的入口，不代表本次发布重新完成生产环境验收。
