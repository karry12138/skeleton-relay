# skeleton-relay（骨架接力）

强模型写骨架，本地弱模型逐任务填实现，脚本负责把关的代码生成工作流。

```
强模型（Cursor 等）                 编排器（本仓库）                          本地模型（aider + vLLM）
──────────────────                  ─────────────────                         ──────────────────────
SPEC.md / 骨架 / 测试 / TASKS.md ─► 按依赖逐个取任务 ─► 生成提示词 ──────────► 只改 files 中的函数体
        打 tag skeleton-v1           接口保护检查 ◄────────────────────────── aider 自动提交
                                     验收测试
                                     通过：标记 done，提交
                                     失败：回滚，带上错误重试（最多 N 次）
                                     仍失败：标记 blocked
强模型审查 / 处理 blocked ◄──────── 汇总 results.json
```

核心思路：**把所有需要判断力的工作前置到骨架里**——接口签名、数据类型、docstring 行为规格、测试、任务拆分与实现要点都由强模型一次写定并冻结；
弱模型每次只看到一个任务的上下文，只需要把 `raise NotImplementedError("T01")` 换成实现。是否完成由测试和接口保护检查判定，而不是由模型自述。

---

## 实测结果

| 项目 | 规模 | 执行模型 | 结果 |
|---|---|---|---|
| `examples/calc`（示例） | 3 个任务、32 个测试 | `deepseek-v4-flash-vision-exp`（本地 vLLM，thinking off，temperature 0） | 3/3 首次通过 |
| 加密货币合约筛选系统（`coin/screener`，不在本仓库） | 29 个任务、297 个测试、约 4000 行 | 同上 | 28 个首次通过；1 个因骨架 docstring 有歧义被标 blocked，补充说明后首次通过；接口违规 0 |

screener 每个任务 30–110 秒，单任务约 12k–35k 输入 token、1k–3k 输出 token。

---

## 仓库结构

```
orchestrator/            编排器
├── __main__.py          命令行：relay validate / list / check
├── tasks.py             TASKS.md 解析、校验（id 唯一、依赖存在且无环、files 不与只读/保护文件重叠）、拓扑排序、回写
├── guard.py             接口保护检查
├── prompt.py            单任务提示词
├── executors.py         调用 aider（模型设置、思考开关、日志、token 统计）
├── runner.py            任务循环：执行 → 检查 → 测试 → 提交 / 回滚重试 / blocked
└── config.py            relay.yaml 加载
scripts/
├── run.py               在已定稿的项目里原地执行接力
└── smoke.py             冒烟：把示例拷进 sandbox/ 建仓库后执行
templates/               SPEC.md / TASKS.md / relay.yaml 模板（规划阶段从这里复制）
examples/calc/           最小示例：四则运算器骨架（3 个任务）
.cursor/rules/           Cursor 规划阶段 Rule（skeleton-relay-planning.mdc）
tests/                   编排器自身的测试
work_md/                 设计讨论与实验记录
```

---

## 安装

需要 Python ≥ 3.11、git，以及一个 OpenAI 兼容接口的模型服务（本仓库实测用 vLLM）。

```powershell
conda create -n skeleton-relay python=3.11 -y
conda activate skeleton-relay
pip install -e ".[dev]"      # 编排器 + pytest，提供 relay 命令
pip install aider-chat       # 执行层（实测 0.86.2）
python -m pytest -q          # 编排器自测
```

> Windows 中文环境：先 `$env:PYTHONIOENCODING = "utf-8"`；不要用 `conda run`（GBK 输出会崩），直接调用环境里的 `python.exe`。

---

## 使用流程

### 1. 规划（强模型）

在 Cursor 中让强模型按 `.cursor/rules/skeleton-relay-planning.mdc` 规划目标项目，产出放在目标项目根目录：

| 文件 | 内容 |
|---|---|
| `SPEC.md` | 目标、范围、设计决策、模块与接口表、数据结构、调用流程、错误处理（模板 7 节） |
| 骨架代码 | 公开签名、类型标注、docstring 全写；函数体只有 `raise NotImplementedError("<任务 id>")`；数据类型/异常/常量直接写完 |
| `tests/` | 覆盖正常路径、边界与每种错误，断言具体值与异常消息；在骨架上应因 `NotImplementedError` 失败 |
| `TASKS.md` | 每个任务一个 ```` ```yaml task ```` 代码块，字段见 `templates/TASKS.md` 注释 |
| `relay.yaml` | 保护文件列表、测试命令、执行模型配置 |

任务拆分原则：一个任务改 1–2 个文件、约 150 行以内；`instructions` 必须自洽（弱模型看不到别的任务）；`acceptance` 写具体 pytest 节点；`depends_on` 只写真实依赖。

自检：

```powershell
relay validate .                    # 格式与依赖
relay list .                        # 依赖顺序，* 为当前可执行
python -m pytest --collect-only -q  # 骨架可导入
```

建议再做一次**依赖闭包检查**：对每个任务，只还原它和它依赖闭包内任务的参考实现，跑它的验收测试——能发现漏写的 `depends_on`。

### 2. 定稿

目标项目必须是**独立 git 仓库的根目录**（编排器会在其中执行 `reset --hard` 与 `clean -fd`，不要放在有未提交工作的大仓库里）：

```powershell
git init -b main
git config core.autocrlf false
git add -A; git commit -m "skeleton: 定稿"; git tag skeleton-v1
```

### 3. 接力执行

```powershell
python scripts/run.py D:\path\to\project                 # 用项目 relay.yaml 中的执行配置
python scripts/run.py D:\path\to\project --thinking high --max-attempts 2
```

开跑前会检查：项目目录是 git 根、工作区干净、骨架 tag 存在。日志与 `results.json` 写在本仓库 `sandbox/<时间>-<项目名>-run/`，不进项目目录。
每完成一个任务，编排器把 `TASKS.md` 中的 `status / attempts / last_error` 回写并提交，因此可以随时中断后重跑，已 `done` 的任务不会再执行。

冒烟测试（拷贝示例到 sandbox 后执行，不碰示例本身）：

```powershell
python scripts/smoke.py --example examples/calc --thinking off
```

### 4. 审查与处理 blocked

- `blocked` 任务的 `last_error` 记录了最后一次的测试输出或接口违规；日志里有每次尝试的提示词与 aider 对话。
  常见原因是骨架规格有歧义：补充该任务的 `instructions`，把 `status` 改回 `todo`、`attempts` 改为 0，提交后重跑。
- 全部完成后由强模型对照 SPEC 审查实现（`git diff skeleton-v1`），重点看测试没覆盖到的行为。
- 手动检查某个任务的改动：`relay check T05 . --base <任务开始前的提交>`。

---

## 接口保护规则（`orchestrator/guard.py`）

| 规则 | 比较基准 |
|---|---|
| `relay.yaml` 中 `protected` 的文件不得有任何改动 | 骨架 tag |
| 任务 `read_only` 中的文件不得有任何改动 | 任务开始前的提交（上游任务已实现的模块可以作为只读参考） |
| 只允许修改任务 `files` 中的文件（`TASKS.md` 除外） | 任务开始前的提交 |
| `files` 中的 `.py`：骨架里已有的函数、类、方法、类字段签名（含默认值、类型标注、装饰器）不得改动或删除；不得新增公开符号，私有 `_` 符号随意 | 骨架 tag |

函数体内部的嵌套定义不计入签名。任一规则违反即视为本次尝试失败，回滚后带着违规信息重试。

---

## relay.yaml

```yaml
skeleton_tag: skeleton-v1
tasks_file: TASKS.md
test_cmd: python -m pytest -q {acceptance}   # {acceptance} 替换为任务的验收节点

protected:          # glob，相对项目根
- SPEC.md
- relay.yaml
- pytest.ini
- tests/*
- src/pkg/models.py

executor:
  kind: aider
  base_url: http://<vLLM 地址>:8888/v1
  model: deepseek-v4-flash-vision-exp
  api_key: sk-local        # vLLM 未开鉴权时随意
  max_attempts: 3
  edit_format: diff
  thinking: "off"          # off | low | high | max；通过 chat_template_kwargs 覆盖服务端默认
  temperature: 0.0         # 写 null 则不发送，使用服务端默认采样
  max_tokens: 32768
  context_window: 1048576
  timeout: 900             # 单次 aider 调用超时（秒）
```

执行层会把 `base_url` 的主机加入 `NO_PROXY`，避免本机代理拦截局域网 / Tailscale 地址。

---

## 已知限制

- 执行层目前只接了 aider；`work_md/` 中有接入 DeepSeek Harness 与迁移到 LangGraph 的方案对比，尚未实现。
- 任务串行执行（同一时间只有一个任务在改仓库）。
- `blocked` 的处理需要人或强模型介入，没有自动升级到强模型。
- 接口保护只覆盖 Python 签名；其他语言只有文件级冻结。
