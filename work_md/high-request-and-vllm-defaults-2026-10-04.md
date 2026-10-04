# DeepSeek-V4-Flash-Vision-Exp High 请求参数 & vLLM 服务默认参数（速查笔记）

> 抓取时间：**2026-10-04 17:58 CST / 09:58 UTC**（`date` 输出）。
> 对象：DSH harness 本地 `llm-dgx-spark` 路由 → `POST http://127.0.0.1:8888/v1/chat/completions` 的 **High** 请求；以及部署在 2× DGX Spark 上的 vLLM（`ghcr.io/anemll/dspark-vllm-gx10:0.1.1`）的**运行中默认参数**。
> 所有默认值均取自 **实时证据**（DSH 源码 + `~/.dsh/settings.yaml` + `docker inspect` 真实命令 + 一次真实 `high` 请求），而非 `.env.example` 的示例默认。

---

## 0. 一句话结论

- **请求侧（DSH）**：`thinking:{type:"enabled"}` + `reasoning_effort:"high"` + `stream:true` + `stream_options.include_usage` + `max_tokens:256000`；**不发送 temperature**。
- **服务端（vLLM）**：`max_model_len=1048576`、`max_num_seqs=6`、`max_num_batched_tokens=8192`、`kv_cache_dtype=nvfp4_ds_mla`、`block_size=256`、`gpu_memory_utilization=0.835`、DSpark `num_speculative_tokens=6`、`--moe-backend flashinfer_b12x`、`tokenizer-mode deepseek_v4`、**`DEFAULT_THINKING=high`**（即 `default-chat-template-kwargs={"thinking":true,"reasoning_effort":"high"}`）。
- 两端思考强度一致，都是 **High**。

---

## 1. DSH harness 发送 High 请求时使用的请求参数

### 1.1 数据路径

DSH 通过 `llm-dgx-spark` 路由访问 vLLM，该路由由 `packages/llm/llm-deepseek/src/dgx-spark.ts` 里的 `registerDeepSeekProvider(ctx, config, {provider:'dgx-spark', …})` 挂载，复用 `DeepSeekAdapter`（`packages/llm/llm-deepseek/src/adapter.ts`）与 `serialize.ts`。

### 1.2 当前生效配置（`~/.dsh/settings.yaml`）

```yaml
agent-default-model:
  provider: dgx-spark
  model: deepseek-v4-flash-vision-exp
  reasoningEffort: high        # ← 默认 High
llm-dgx-spark:
  baseURL: http://127.0.0.1:8888/v1
  models:
    - id: deepseek-v4-flash-vision-exp   # 未声明 maxTokens → 回落到 256000
      name: DeepSeek-V4-Flash-Vision-Exp
      contextWindow: 1000000
      inputModalities: [text, image]
      imagePixelBudget: 640000
      imageMaxBytes: 1048576
```

### 1.3 实际打出的请求体

`serialize.ts` 的 `serializeRequest` / `requestWithMessages` 组装：

```jsonc
{
  "model": "deepseek-v4-flash-vision-exp",
  "messages": [ ... ],                    // system/user/assistant/tool 轮次，含 reasoning_content 回传
  "stream": true,
  "stream_options": { "include_usage": true },
  "thinking": { "type": "enabled" },       // resolveThinking: effort=="high" → enabled
  "reasoning_effort": "high",              // ← High 映射
  "tools": [ ... ],                        // 仅当有工具调用声明时出现
  "max_tokens": 256000,                    // ← 见 1.4
  // "temperature" 不发送（undefined）→ 走 vLLM 服务端默认
  // "stop" 不发送（除非显式配置）
}
```

### 1.4 关键字段来源

| 字段 | 值 | 依据 |
|---|---|---|
| `reasoning_effort` | `"high"` | `agent-default-model.reasoningEffort: high`；`resolveThinking`（`serialize.ts:83-99`）把 `high` 解析为 `{ thinking:'enabled', reasoningEffort:'high' }`，两者都走**顶层**（不在 `extra_body` 内） |
| `thinking` | `{ "type":"enabled" }` | 同上 |
| `max_tokens` | `256000` | agent 自身未设 `maxTokens`；`DeepSeekAdapter.modelInfoFor`（`adapter.ts:418`）给 `defaultMaxTokens = connection.maxTokens`；`llm-dgx-spark` 的该 model 未声明 `maxTokens`，回落到 `DEFAULT_MAX_TOKENS = 256_000`（`adapter.ts:151`、`index.ts:428`），再经 `resolveCallWithInfo`（`llm/src/index.ts:876`）自动填充并上送 |
| `temperature` | **不发送** | `serialize.ts:367` 仅在 `options.temperature !== undefined` 时写入；整条调用链无默认值 → vLLM 服务端默认采样 |
| `stream_options` | `{"include_usage":true}` | 固定写死（`serialize.ts:361`） |

额外说明：请求头还携带 `x-deepseek-harness-user-id`、`x-deepseek-harness-session-id` 及 attribution headers（`adapter.ts:541-553`）。

### 1.5 实测验证

向 `:8888` 发了一次 `thinking:enabled` + `reasoning_effort:high` 请求，返回 `HTTP 200`，首块为 `delta.reasoning`，确认服务端接受并启用思考（`high` 生效）。

---

## 2. 部署的 vLLM 服务默认参数

取自**运行中容器**（`docker inspect`，`deepseek-v4-flash-vllm-dspark-1`，已运行 4 天，`Up (healthy)`）的**真实启动命令**：

```
vllm serve deepseek-ai/DeepSeek-V4-Flash-Vision-Exp
  --served-model-name deepseek-v4-flash-vision-exp
  --host 0.0.0.0 --port 8888 --trust-remote-code
  --tensor-parallel-size 2 --pipeline-parallel-size 1
  --kv-cache-dtype nvfp4_ds_mla --block-size 256
  --max-model-len 1048576          # 1M 上下文上限
  --max-num-seqs 6
  --max-num-batched-tokens 8192
  --long-prefill-token-threshold 1024
  --max-cudagraph-capture-size 42   # 6*(6+1)；注释指出引擎会截断到 40
  --gpu-memory-utilization 0.835
  --enable-prefix-caching --enable-prompt-tokens-details
  --async-scheduling --enable-chunked-prefill
  --speculative-config '{"method":"dspark","num_speculative_tokens":6,"draft_sample_method":"probabilistic"}'
  --tokenizer-mode deepseek_v4
  --limit-mm-per-prompt '{"image":16}'
  --distributed-executor-backend mp
  --moe-backend flashinfer_b12x
  --tool-call-parser deepseek_v4 --enable-auto-tool-choice
  --reasoning-parser deepseek_v4
  --reasoning-config '{"reasoning_parser":"deepseek_v4","reasoning_start_str":"🤔","reasoning_end_str":"🤔"}'
  --default-chat-template-kwargs '{"thinking":true,"reasoning_effort":"high"}'
  --generation-config vllm --enable-flashinfer-autotune
  --nnodes 2 --node-rank 0 --master-addr 10.100.48.2 --master-port 25000
```

### 2.1 运行中环境变量（容器内实际值）

```
DEFAULT_THINKING=high          # 注意：示例 .env 默认是 low，当前运行是 high
MTP_NUM_TOKENS=6
VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
```

`GET /v1/models` 返回 `max_model_len: 1048576`、`id: deepseek-v4-flash-vision-exp`。

### 2.2 与仓库示例默认（`.env.dspark.example`）的差异

| 项 | 仓库示例默认 | **当前运行** |
|---|---|---|
| `DEFAULT_THINKING` | `low` | **`high`** |
| `LIMIT_MM_PER_PROMPT` | `image=8` | **`image=16`** |
| `GPU_MEMORY_UTILIZATION_TEXT` | `0.835` | `0.835`（一致） |
| `MAX_NUM_SEQS` | `6` | `6`（一致） |
| `MAX_MODEL_LEN` | `1048576` | `1048576`（一致） |

### 2.3 服务端对 `reasoning_effort` 的映射（boot 补丁）

容器启动时对 `deepseek_v4` tokenizer 打补丁（docker-compose command 里那段 `python3 -c …`），把原本的 `else: reasoning_effort="high"` 改为：

```python
elif reasoning_effort in ("max","xhigh"): reasoning_effort = "max"
elif reasoning_effort == "high":          reasoning_effort = "high"
else:                                     reasoning_effort = "low"
```

即：`high` → `high`（显式生效）、`max/xhigh` → `max`、其余 → `low`。
注意：前端编码器会按 effort 在 BOS 后插入 directive（`high` 约 80 token，`max/xhigh` 约 93 token，`low/off/medium` 为 0）。

---

## 3. 参考来源

- DSH 源码（本地 checkout `/home/elderman/elderman/database/dsh`）：
  - `packages/llm/llm-deepseek/src/dgx-spark.ts`（`dgx-spark` 路由挂载）
  - `packages/llm/llm-deepseek/src/adapter.ts`（`DEFAULT_MAX_TOKENS=256000`、`resolveModelInfo` 的 `defaultMaxTokens`）
  - `packages/llm/llm-deepseek/src/serialize.ts`（`resolveThinking`、`requestWithMessages` 的 wire 字段）
  - `packages/llm/llm/src/index.ts`（`resolveCallWithInfo` 自动填充 `maxTokens`/`reasoningEffort`）
  - `packages/core/agent-default-model/src/index.ts`（`agent-default-model.reasoningEffort`）
- DSH 运行配置：`~/.dsh/settings.yaml`
- 部署仓库：`how_to_deploy_dsv4f_on_2dgxspark/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark/`（`docker-compose.dspark.yml`、`.env.dspark.example`）
- 运行时证据：`docker inspect deepseek-v4-flash-vllm-dspark-1`、`GET /v1/models`、一次真实 `high` 请求（HTTP 200）

---

> 免责声明：本笔记为 2026-10-04 快照；若后续修改 `DEFAULT_THINKING`、`MAX_NUM_SEQS`、`GPU_MEMORY_UTILIZATION_TEXT` 或 DSH 配置，需重新核对。
