# ProofNav M2.1 Online / Offline Dependency Boundary

## 1. 依赖方向

```text
                 proofnav.contracts + proofnav.validation
                         ^                    ^
                         |                    |
proofnav.runtime/{semantics,state,...}   proofnav.offline/{oracle_evidence,
                                          structural_audit,oracle_verifier}
```

Runtime 不导入 `proofnav.offline`、oracle provider、controlled truth 或 evaluator。生产公共入口仅
导出 `ProofState/CertificateBuilder/OnlineVerifier/TerminalController`。

Offline structural auditor 是刻意独立的第二实现：它不得 import/call runtime semantics 或 online
verifier，只共享 frozen contracts 的 schema constants、canonical JSON/SHA-256 和 M1 validators。
这避免 online 的同一个 bug 同时“验证”自己。共同的 adversarial corpus 用来检测两份实现 drift。

## 2. 两个 code-owned admission profile

Production profile 精确固定：

```text
producer      = proofnav.adapters.sanitize_duet_observation
source schema = duet.reverie._get_obs@frozen-m0
interface audit SHA-256
  2d2cf87d402b7d6e7283bf86c5da56cacd49312359d367c8c5d6234dbe9b47b8
evidence      = production_zero
identity link = production_zero
```

Controlled profile 精确固定为 `proofnav.offline.controlled_replay`、
`proofnav.controlled-observation.v2` 与 synthetic micro audit。Profile 是代码注册值，不接受调用方
prefix、allowlist alias 或任意 audit ref。Production verifier 对 controlled profile 永远拒绝。

Exact profile 只声明进程内 contract 信任边界，不是网络攻击者的数字签名。本阶段没有远程/多进程
attestation；若部署威胁模型需要跨进程真实性，后续必须增加签名 admission envelope，而不能把
`producer` 字符串宣传成密码学证明。

## 3. Decision audit bundle

State 向 verifier/offline 交付 frozen bundle：

```text
schema_version
scope, template, admission_profile, risk_claims
raw proof transitions
claimed derived state
bundle_digest
```

Runtime verifier 和 offline auditor都必须从 raw transitions 重算 claimed state。Caller 修改 derived
frontier、closure、budget、cost 或 universe 不会改变 raw cause，只会造成 bundle mismatch；caller
修改 raw observation/candidate 又会破坏 transition/bundle/certificate identity。证书只在一个 exact
decision cut 有效。

Exact observation interface 同时绑定 panorama `[36,D] float32`、view/candidate point index
`[0,35]`、candidate `[D] float32`、唯一 object IDs 与 `[N,768]/[N,4]/[N,3] float32` object
schemas，以及 template/observation instruction digest 一致。

## 4. Truth 和 evidence 的单向流

```text
ControlledTruth (hidden fact)
              |                 ControlledEvidenceScript (predicate output)
              |                                  |
              v                                  v
      offline comparison              OracleEvidenceProvider
                                                 |
                                    bound evidence v2 + M1 evidence v1
                                                 |
                                    controlled replay state only
```

Truth 不再驱动 evidence emission。Script 可在测试中模拟 factual predicate error，而 truth 本身仍
必须内部一致。Runtime bundle、certificate、online feedback 与下一动作均不含 semantic truth、GT
path/object、supported/refuted truth set 或 evaluator aliases。Offline outcome 的
`feedback_to_runtime` 永远为 null。

Identity association 也遵守单向边界：M2.1 controlled identity witness 只在 replay profile 中开放，
精确绑定两端 unit/source observation provenance，强制跨 viewpoint 与 component injectivity，并计入
query/ledger cost；`SAME_ENTITY` 的事实正确性不由 unit ID 自证。Production identity admission
保持 zero，真实 identity adapter 与 factual validation 属于后续感知阶段。

## 5. M0/M1 与 DUET 边界

- M1 observation/evidence/scope/obligation/certificate/result v1 字段集合保持冻结；M2.1 全部新增语义
  使用显式 successor versions/wrappers。
- M0 fixed six-event trace 与 legacy M1 contracts 继续做 CPU regression；本轮不重跑 M0。
- `map_nav_src/`、原 rollout、STOP、prediction/evaluator 没有在 M2.1 接线或修改。
- M2.1 controlled accounting 不冒充 global path expansion 成本；M4 必须用真实 ACTION/execution
  events 升版后才能接正式 DUET rollout。
- 没有下载、GPU、训练、正式 paired 数据或 benchmark。
