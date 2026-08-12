# ProofNav M2 代码驱动微调记录

> 日期：2026-08-12（UTC）  
> 限制：只保留两个 M2 内生增强；不增加研究主线或提前实现 M3/M4。

## Conformance 修复：固定真实 M0 trace slice

- 原状态：M1 mandatory suite 会机会性读取未跟踪 `.m0-results`；本机存在时检查 66 events，
  clean checkout 则 skip。
- 代码事实：测试不失败，但结果依赖本机 artifact 是否存在，不满足 mandatory reproducibility。
- 调整：固定一个从实测 trace 做字段投影和标识脱敏的 6-event observation→action→execution→
  endpoint slice；源文件 SHA-256 为
  `70c61e3afc17a5b093c234f33967df28c55308718ee5e1364270d41728509093`。完整本机检查移至
  `tests/integration/`，必须显式提供开关和路径。
- 影响：M1 仍为 27 tests，语义未改变；干净 checkout 不再依赖 `.m0-results`。

## E1：生产 evidence admission 在 M2 采用 zero-admission

- 原设计：用 adapter prefix 加 oracle/fixture token denylist 区分生产和 replay。
- 反例：oracle evidence 可同时重命名 adapter、producer、dependency group 与 source field，
  仅靠字符串策略无法证明来源真实。
- 候选：A）把 hidden truth 交给 online verifier（破坏 firewall）；B）配置 allowlist（同样可伪造）；
  C）M2 production zero-admission，M3 以代码拥有的 adapter 边界和新版本开放；D）依靠 offline
  auditor 事后补救（不能保护 runtime）。
- 选择：C。它是当前无真实 perception adapter 时唯一 fail-closed 的方案；controlled replay
  仍复用正式 M1 evidence contract。
- 影响：M2 只声称 controlled evidence 下逻辑闭环；M3 必须显式升级 admission，不得通过配置
  打开。论文 claim 被收紧而非扩大。

## E2：semantic digest 与 ordered audit chain 分离

- 原设计张力：append-only hash chain 必然依赖 evidence 到达顺序，但证书对同一 evidence set
  应稳定且不依赖排列。
- 候选：A）证书直接绑定 chain tip（破坏 permutation invariance）；B）只排序 evidence，丢失
  时序审计；C）保留 ordered append/revoke chain，同时对 sorted active set 计算 semantic
  ledger/proof digest。
- 选择：C。证书绑定 semantic digest 和 event count；proof snapshot audit trail 独立保存 chain
  tip。revoke 会改变 active set/digest，旧证书仍会 stale。
- 影响：同一 evidence 集合得到字节稳定证书，同时保留删改/撤销审计；不改变方法主线，属于
  certificate canonicalization 的 M2 收紧。

## 检查后无需调整

- M1 strict schema、branch-aware action、observation provenance、三状态与 legacy DUET 语义可直接
  支撑 M2，无需升版或放宽；
- 不需要修改 DUET rollout：standalone terminal/replay harness 已能验证 gate；
- scope-relative NOT_FOUND、frontier 与 forced UNRESOLVED 的定义未发现内部矛盾。
