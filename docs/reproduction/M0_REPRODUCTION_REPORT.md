# M0 DUET REVERIE 兼容复现报告

> 日期：2026-08-12（UTC）
>
> 结果：**A — M0 完成**

配套文档：[资源清单](M0_RESOURCE_MANIFEST.md)、
[环境冻结](M0_ENVIRONMENT_LOCK.md)、[trace schema](M0_TRACE_SCHEMA.md)。

## 1. 资源与兼容环境

- DUET 官方 archive 已保留在
  `/root/autodl-tmp/ProofNav/.m0-staging/download/datasets.zip`：
  20,121,983,052 bytes，SHA-256
  `362aefa62a8f57dcab0f6d7475a0818f1cc140357b31fa6806346075d34effe8`；
- archive 的 167 个成员完成路径、重复名、symlink、CRC 和必需路径审计；
  Dropbox 额外的零长度根目录成员 `/` 被受控 extractor 显式跳过；
- 只提取 101 个 M0 所需文件；R4R、SOON、预训练 annotation/model 均未落地；
  raw Matterport3D scan、LXMERT 和 BERT base weights 均未下载；
- panorama HDF5 有 10,567 个 `(36, 1768)` key，覆盖全部 REVERIE
  connectivity viewpoint；object HDF5 有 7,003 个 key，feature/attribute schema
  全通过；
- checkpoint 含 429 个 VLN-BERT tensor 与 4 个 critic tensor，两组件对 dynamic
  模型 strict load 通过；checkpoint SHA-256
  `c74aad4b4c330785c945844ba6a30490962623e938843477e0d062459a9918dc`；
- 完整 101 文件 hash manifest 位于
  `/root/autodl-tmp/ProofNav/.m0-results/audits/resource_hash_manifest.json`
  （manifest SHA-256
  `db835cf71e51109b5aff5adc4cf5904171232fe21c6e6f47f83efd0ee3bf8510`）。

环境为 Python 3.8.10、PyTorch 2.0.1+cu118、CUDA 11.8 build，RTX 4080
SUPER CUDA tensor smoke 通过。它与历史官方 torch 1.7.1+cu101 不同，属于 Ada
GPU 必要的兼容复现，而不是 bitwise 历史环境复现。完整版本和 pip 配置见
[M0_ENVIRONMENT_LOCK.md](M0_ENVIRONMENT_LOCK.md)。

官方 recursive MatterSim checkout 使用 OSMesa，全目标构建和 import/config smoke
通过。Ubuntu OpenCV 4.2 只需要两处旧常量的同语义 namespace 替换，补丁冻结在
[M0_MATTERSIM_OPENCV4.patch](M0_MATTERSIM_OPENCV4.patch)。

## 2. 原始 DUET baseline

从 `map_nav_src` 执行官方 test 参数；唯一行为无关扩展是把 evaluator metrics 写入
独立文件：

```bash
CUDA_VISIBLE_DEVICES=0 python reverie/main_nav_obj.py \
  --root_dir ../datasets --dataset reverie \
  --output_dir ../.m0-results/baseline/dynamic_seed0 \
  --world_size 1 --seed 0 --tokenizer bert \
  --enc_full_graph --graph_sprels --fusion dynamic --multi_endpoints \
  --dagger_sample sample --train_alg dagger \
  --num_l_layers 9 --num_x_layers 4 --num_pano_layers 2 \
  --max_action_len 15 --max_instr_len 200 --max_objects 20 \
  --batch_size 8 --features vitbase --obj_features vitbase \
  --image_feat_size 768 --angle_feat_size 4 --obj_feat_size 768 \
  --resume_file ../datasets/REVERIE/trained_models/best_val_unseen \
  --test --submit \
  --offline_metrics_file ../.m0-results/baseline/dynamic_seed0/offline_metrics.json
```

没有执行官方 shell 中位于 test 之前的训练段。

### 2.1 Validation 指标

| split | SR | SPL | RGS | RGSPL | DUET 论文表 6 | 差异 |
|---|---:|---:|---:|---:|---|---|
| val_seen | 71.75 | 63.94 | 57.41 | 51.14 | 71.75 / 63.94 / 57.41 / 51.14 | 报告精度下 0 |
| val_unseen | 46.98 | 33.73 | 32.15 | 23.03 | 46.98 / 33.73 / 32.15 / 23.03 | 报告精度下 0 |

更高精度值在
`/root/autodl-tmp/ProofNav/.m0-results/baseline/dynamic_seed0/offline_metrics.json`
（SHA-256 `d1c58821...a6aa10d`）。论文对照来自 DUET 官方论文 Table 6：
<https://arxiv.org/pdf/2202.11742>。

正式运行 wall time 754.89s，峰值进程 GPU memory 6,264 MiB，峰值进程 RSS
3,431,772 KiB。完整命令/计量和 stdout/stderr 分别在
`.m0-results/measurements/official_dynamic_batch8.json` 与
`.m0-results/logs/official_dynamic_batch8.log`。

### 2.2 Prediction 完整性

| split | prediction 数 | 唯一 ID | SHA-256 |
|---|---:|---:|---|
| val_train_seen | 123 | 123 | `ebc17f06...e7dda55` |
| val_seen | 1,423 | 1,423 | `800c4106...43523f` |
| val_unseen | 3,521 | 3,521 | `663bd47a...bc425` |
| test | 6,292 | 6,292 | `e683437e...b60cc6` |

每项只有原格式 `instr_id/trajectory/pred_objid`，无空轨迹。test 没有本地 GT，
没有产生 test metrics，也没有上传 leaderboard。

## 3. Runtime trace 与无泄漏验证

真实 dynamic trace：
`/root/autodl-tmp/ProofNav/.m0-results/traces/dynamic_runtime_trace.jsonl`，
SHA-256 `70c61e3afc17a5b093c234f33967df28c55308718ee5e1364270d41728509093`。

- 固定 episode：`6617_185_1`；66 events；
- 14 observations、13 model_scores、13 actions、13 terminations、12 executions、
  1 prediction；
- tracing off/on prediction 文件 SHA-256 均为
  `c2da2341f9854aba0e55fda34cccae79730eaa1266e8433081ecb37b513917d6`；
- canonical trajectory、由原轨迹规范化的逐步 action、`pred_objid` 全相同；
- 第二次 traced repeat 的原始 action 序列也完全相同；
- typed allowlist、event sequence/causality、action ID/mask mapping、termination
  priority 和递归禁字段审计均为 0 failure；
- sink 不持有 observation/environment/simulator/evaluator/GraphMap 引用；
- `runtime_trace.jsonl` 无 evaluator event/metrics/GT/full connectivity；metrics 在
  另一目录物理分离，policy 和 sink 不读取该文件。

同一固定 episode 还分别运行 local/global/dynamic：STOP 都是 index 0/null；local
动作映射 `[STOP]+candidate`，global/dynamic 映射 `[STOP]+gmap viewpoint`，三个
模式审计均通过。真实 dynamic trace 捕获一个不含 source 的 4-hop execution suffix，
前三个节点只标 `travel_only`，最后 endpoint 才产生下一 observation。

首次 candidate 含用于选择代表视角的 angular `distance`，cache candidate 不含；
两者 candidate IDs 和全部决策字段一致，agent 没有读取 candidate `distance`。

## 4. Offline adjacency audit

审计范围是五个 REVERIE annotation split 涉及的全部 86 个 scan、10,318 个
included viewpoint 和 41,732 条有向合法 connectivity edge。每个 viewpoint 的
MatterSim 36-view candidate union 与合法 unobstructed neighbors 比较结果：

- missing neighbors：0；
- extra neighbors：0；
- mismatch viewpoints：0；
- observation-interface candidate completeness contract：通过。

该 audit wall time 7.06s、峰值 RSS 246,372 KiB、GPU 0 MiB；truth 只写入
`.m0-results/audits/adjacency.json`，从未进入 runtime trace 或反馈给 agent。

## 5. 源码与文档变更

- `runtime_trace.py`：默认关闭的 typed/sanitized JSONL sink；
- `agent_obj.py`：只读 observation/model/action/execution/termination/prediction 接缝；
- `parser.py`、`main_nav_obj.py`：默认关闭的 trace/offline metrics 与 M0 最小 split/
  iteration 开关；默认官方 validation 行为不变；
- `m0_*_audit.py` 与 `m0_run_measure.py`：archive、资源、strict checkpoint、candidate
  cache、trace、adjacency、hash 和运行成本的离线审计；
- `.gitignore`：阻止受条款约束的 staging/cache/results/data 被误纳入版本控制；
- `AGENTS.md` 和项目/M0 文档按本轮约束更新。

没有修改模型架构、checkpoint、数据内容、action selection、STOP、trajectory 或
evaluator 语义。trace 默认关闭的逐字节 prediction 等价性已经实测。

## 6. 失败记录与 M0 判定

已闭合的兼容问题：MatterSim 两个 OpenCV 4 常量；tensorboardX 2.4.1 与 protobuf
5 的冲突（固定 protobuf 3.20.3）；archive 的 inert `/` member；test split 无
`path_id` 是官方匿名 schema，不是数据损坏。一次无收益的同版本 PyPI 重装已按事实
记录，不再重复。

M0 完成标准全部满足：环境/MatterSim/数据/checkpoint 冻结、原始 baseline 全量运行、
validation 指标复现、test predictions、真实无 GT trace、on/off 等价、三 fusion 映射、
candidate cache 和全量 adjacency audit 均完成。**没有进入 M1。**
