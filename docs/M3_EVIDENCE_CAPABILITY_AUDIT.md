# M3-A DUET evidence capability audit

> 日期：2026-08-12（UTC）  
> 证据：当前源码、本地 frozen resources、已有真实 M0 micro trace；不是 benchmark 结果

## 1. 真实 signal chain

`ReverieObjectNavBatch._get_obs` 在实际到达 viewpoint 后生成 panorama `[36,772]`、candidate `[772]`
和 object `[N,768]/[N,4]/[N,3]`，同时原 dict 也混有 `gt_path/gt_end_vps/gt_obj_id/distance`。
`sanitize_duet_observation` 只复制 shape/dtype、slot IDs 和 allowlisted metadata，正确去掉 GT，但也不保存
feature/logit values。

`forward_navigation_per_step` 返回 `gmap_embeds/vp_embeds/global/local/fused logits/obj_logits`；真实接缝
在 `agent_obj.py` 的 `nav_outs` 形成之后、action 选择之前。object logits 是共享 text-conditioned local
encoder 后的 grounding head 输出。M0 trace 实际保存 ordered proposal IDs、mask 和 logits，但未绑定
feature、instruction、checkpoint 或 calibration digest。

Object HDF5 原数组为 `N×1768 float64`；runtime 取前 768 维并 cast `float32`，directions/sizes 变成
angle/box features。HDF5 attrs 还含 `names/depths`，当前 runtime 不返回，M3 不把它们新增成在线信号。

## 2. Proposal provenance collision

本地只读 audit 对全部 10,559 个 `BBoxes.json` viewpoints 和 7,003 个非空 object-HDF5 keys 对照：
HDF5 `obj_ids` 与 BBoxes object inventory 0 mismatch、0 extra key，并带对应 names。因此现有 slots 更接近
benchmark annotated-box features，而不是独立 detector proposals。

本轮 entity claim 必须写成 **annotated-slot grounding**。它不证明 detector discovery、开放世界枚举或
residual completeness。BBoxes、`obj2vps`、`gt_obj_id` 和路径只允许进入 offline label builder/auditor。

## 3. Capability matrix

| 能力 | 真实在线输入 | offline label | 当前可支持 claim | 状态/缺口 |
|---|---|---|---|---|
| entity | slot 768-D feature、angle/box、full finite object logits、mask、instruction | `gt_obj_id/gt_end_vps` | annotated-slot SUPPORT/ABSTAIN | 需 extractor+artifact；REFUTE sealed |
| attribute | slot/cross-modal embedding可能隐含属性 | REVERIE无结构化标签 | 无 | 需 paired labels+轻量 head；ABSTAIN |
| relation | 共视角 slots、angles/size、joint embeddings | 无 relation/anchor truth | 无 | 需 pair head+显式 label；ABSTAIN |
| room_anchor | panorama/map embedding、pose、instruction | 无 room/region contract | 无 | 需新非-GT signal/labels；ABSTAIN |
| residual coverage | 36-view features、proposal set、topology | BBoxes只能审 frozen inventory | topology closure only | semantic coverage sealed；UNRESOLVED |
| SAME_ENTITY | 跨视角 features、pose、angle/size | ID可作 offline pair label | 无 | feature re-ID与false-link calibration缺失；zero admission |

## 4. Score semantics与相关性

Object loss只在当前 viewpoint属于 `gt_end_vps`时监督目标 slot；其余 viewpoint整项为 ignore index。因此
低 object logit不是 entity absence。真实 M0 trace还含单个错误 proposal的 observation，object softmax
在该处必为 1；所以 softmax/top-1/margin不是校准证据。

同 observation 的 views/objects共享 panorama transformer、text encoder与head；同 viewpoint revisit
重用底层 HDF5 feature；跨 viewpoint同一 annotated object的crop feature也相关。初始 dependency lineage
至少覆盖 source observation，revisit和identity component不得产生独立性折扣。

已有 micro trace `6617_185_1` 只证明 signal path：13 个 model-score events，目标 slot 185 在 step 12
出现且 logit约 3.9348；这不是 threshold、accuracy或calibration结果。

## 5. 资源 identity

| artifact | bytes | SHA-256 |
|---|---:|---|
| panorama HDF5 | 3,141,482,913 | `ae0ff208349e6a12096fe47c7b045e42b93e9c047da50d19dd17e04ec8d31bbc` |
| object HDF5 | 259,365,852 | `9d9f591f64d98a3547035575803fa0e78e779a57a06dd34467e480373c26b615` |
| BBoxes | 7,757,728 | `21d227018de2e11eb0a7b3188d760a56a988e8152213d15979ba6ba7a0e58296` |
| DUET checkpoint | 2,175,032,658 | `c74aad4b4c330785c945844ba6a30490962623e938843477e0d062459a9918dc` |
| M0 real trace | 149,304 | `70c61e3afc17a5b093c234f33967df28c55308718ee5e1364270d41728509093` |
| adjacency audit | — | `2d2cf87d402b7d6e7283bf86c5da56cacd49312359d367c8c5d6234dbe9b47b8` |

## 6. Minimal slice boundary

首片读取真实 DUET full object-logit vector及post-cast feature digest，经 code-owned adapter和offline-only
artifact只产生 entity SUPPORT/ABSTAIN。若“non-oracle”要求proposal localization本身也不得使用GT box，
则现有资源不足；需要有生成provenance的非-GT detector proposals，或raw RGB+获批detector checkpoint。

## 7. 实测 signal extraction 与能力结果

2026-08-13 在预注册的 `val_train_seen`、seed 0、4 batches×8 上运行默认关闭的 extractor；终审先修复
ended-batch 重复发射，再将含 `objId` 的 REVERIE `instr_id` 替换为仅由
`(scan,start_viewpoint,instruction)` 派生的 opaque runtime episode key。最终得到 193 条 active records、
32 episodes、21 scans，JSONL SHA-256 为
`43874168338d349e90c4111a21829552f68cfe4c33ba28240a832054b42c03bd`。每条记录都绑定：

- ordered slot IDs、full finite object logits 与 boolean valid mask；
- 实际送入模型的 panorama/object/angle/box/instruction post-cast content digest；
- checkpoint/model/feature/interface/config/tokenizer identity；
- 当前 sanitized observation、instruction 和 code-owned entity template。

57/193 observations 没有有效 slot（development/calibration/demonstration 分区分别为 24/10/23），全部
保持 null selection 并 ABSTAIN，没有被当作负证或从 calibration denominator 中删除。

阈值 3.0 的 calibration 分区有 13 次 SUPPORT 机会，其中 2 次为 false support，且分布在
2/6 scans；这直接否定了“frozen absolute logit 在常用 `alpha_F=0.05` 下足够”。
因此 capability matrix 的最终 M3-A 结论是：

| capability | M3-A production result |
|---|---|
| entity annotated-slot SUPPORT | 已开放，但仅 exact seen-scan artifact domain；派生描述性 risk `1/3` |
| entity REFUTE | sealed |
| attribute / relation / room | ABSTAIN |
| location / anchor residual coverage | OPEN；NOT_FOUND sealed |
| SAME_ENTITY | production zero-admission |

该结果证明信号接缝和 fail-closed 机制真实工作，不证明当前 signal 已达到有用的
风险—覆盖折衷。
