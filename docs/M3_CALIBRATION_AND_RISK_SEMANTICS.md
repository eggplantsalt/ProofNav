# M3 calibration artifact and certificate-risk semantics

## 1. Artifact authority

Calibration artifact是code-owned、canonical-hash sealed的aggregate object，至少绑定：evidence family与
polarity、score transform、model/checkpoint/feature/interface/config/tokenizer hashes、label-definition
digest、scan split fingerprint、calibration method/parameters、validity domain/shift policy、sample与
dependency unit、risk event、bound/confidence语义、aggregate counts、生成命令与producer。

它不得包含逐样本truth、目标路径、完整connectivity或runtime可查询的GT map。结构校验与生产授权是两层
不同API：offline builder可以构造并检查candidate aggregate，但只有artifact digest已经进入code-owned、
自身由源码常量封印的registry manifest时，production adapter/state/online verifier与独立offline
structural auditor才承认其authority。仅由调用方重算artifact digest（即使counts与更小bound内部一致）
仍以`M3_ARTIFACT_NOT_REGISTERED`拒绝。Runtime随后还要重验exact schema、model/signal identity和domain。
Production registry只包含tracked real aggregate；synthetic/test artifact不得进入authority allowlist。
当前唯一条目是`real-descriptive-seen-scan-m3a-micro`，其exact JSON、artifact digest、source revision和
manifest seal均随源码冻结。Contract tests也复用这份真实registered artifact；需要不同bound/threshold的
candidate只能走structural validation或验证production拒绝，不能用test patch或escape hatch授权。

## 2. M3-A artifact semantics

首个artifact只允许：

```text
family            = duet_annotated_slot_entity_grounding
polarity          = SUPPORTS
decision          = selected absolute logit passes frozen rule
sample unit       = scan-familywise
domain            = descriptive_seen_scan_micro
shift policy      = exact domain match or ABSTAIN
```

它不提供entity REFUTE、coverage、identity、attribute、relation或room risk。当前checkpoint/data split不
支持unseen guarantee，因此micro artifact的bound必须标为descriptive/compatibility，不宣传为held-out
statistical guarantee。正式artifact将使用scan-disjoint calibration与预注册one-sided bound/CRC。

## 3. Signal/evidence binding

Signal record绑定source observation/event/content digest、ordered proposal IDs/mask、完整finite logits、
selected slot/statistic、post-cast panorama/object feature digest、instruction encoding/template digest、
model/checkpoint/config/tokenizer/interface/artifact hashes及signal digest。重排proposal、改任一value/hash或
换template均使旧decision stale。Panorama digest绑定DUET实际candidate-first packed model input；其行数为
`len(candidates) + 36 - len(unique candidate point_id)`，因此多个candidate共享point ID时可以大于36。

Adapter decision绑定query/hypothesis/obligation/typed subject/location、signal、artifact、domain结果、
SUPPORTS/REFUTES/ABSTAIN、code-derived dependency lineage和risk atom。ABSTAIN不进入M2 evidence ledger。

## 4. Derived composition

M3 production state不接受caller `risk_claims`。Composer只从certificate实际选择的active calibrated
evidence/link/residual atoms重算。首版只存在SUPPORT atoms，因此只能形成FOUND risk；NOT_FOUND没有
完整risk atoms时必须UNRESOLVED。

Atom顺序不影响digest/risk；同evidence跨certificate复用保留同一atom与accounting；revocation移除active
atom但不删除历史cost；exact revisit不降低risk。Caller提交更小upper bound、错误polarity或任意
dependency group均被拒绝。

## 5. Fail-closed table

| 输入 | 结果 |
|---|---|
| 无artifact的logit | proposal only / ABSTAIN |
| unsupported predicate或REFUTES | ABSTAIN |
| empty proposals、STOP、low logit、no frontier | residual OPEN |
| NaN/Inf、缺字段、digest mismatch | reject/ABSTAIN |
| unseen/out-of-domain scan | ABSTAIN |
| duplicate/revisit evidence | risk不下降 |
| missing location/anchor residual | NOT_FOUND拒绝 |
| uncalibrated identity/object-ID equality | no link |

## 6. 已注册真实 micro artifact

M3-A production registry 只授权一个真实 aggregate artifact：

```text
artifact digest  d2548e03e38c24423f846c372d66ed0abd1dc78b672bf9f6c965566d699f830f
threshold        selected absolute object logit >= 3.0
calibration      6 scans / 54 active observations / 2 error scans
null outputs     10 (retained as no-SUPPORT opportunities)
bound            1/3 descriptive scan-familywise frequency
confidence       none
domain           exact 8 predeclared seen-scan demonstration IDs, else ABSTAIN
```

Synthetic test artifacts不在production registry中；测试链同样读取这个exact tracked artifact。
Scope的`calibration_version`必须精确等于
`proofnav.calibration-artifact.v1:<artifact_digest>`，不允许把已注册atom附在generic或其他
calibration version下。

这个 registry 是代码内 trust anchor：它防止调用方用自己的 counts/bound 重签一个更小risk。M3-A还把
corrected active-only source JSONL的SHA-256、固定partition rule、72个applicability-partition signal
digests和scan set封入独立signal manifest，并把该manifest的canonical digest再次封入registry。
Production成功链因此只接受这个fixed recorded micro replay里的exact signals；公开
`build_duet_signal`生成的自洽synthetic或任意resealed high-logit object都以
`M3_SIGNAL_NOT_REGISTERED`拒绝。

这不是live inference的通用authority，也不是密码学硬件attestation。要让未来新在线signal获得
production authority，仍需受信in-process capability或外部签名/attestation与独立资源验证。当前claim
严格限于fixed recorded micro replay和descriptive compatibility，不能外推为新episode、unseen scan或
任意live process的统计保证。

终审进一步撤销了“无GT fixed replay authority”这一措辞：REVERIE原始`episode_id`采用
`pathId_objId_instrIdx`，因此corrected signals及event lineage仍直接携带target object ID；canonical demo
ordering也读取了这个字段。Registry只能证明这些含semantic alias的bytes没有被调用方替换，不能把它们
变成无GT输入。另一个机械边界是当前manifest只认证wrapper中的exact evidence signal；此前
`OBSERVATION` prefix仍只受schema/causal checks约束，并非逐条registered replay。故本节数字只能支持
artifact/signal membership、adapter、risk、certificate和verifier机制回放，不能支持完整真实prefix或无GT
production claim。修复需要在sanitizer前生成offline-isolated opaque episode/event pseudonym，并为完整M3
observation prefix建立artifact-specific seal；随后必须重建interface、signals、artifact、manifest和registry。
