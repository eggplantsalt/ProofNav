# ProofNav M2 Online / Offline Dependency Boundary

## 1. 允许依赖方向

```text
proofnav.contracts + proofnav.validation
             ^
             |
proofnav.runtime/{state,certificate,verifier,terminal}
             ^
             |
proofnav.offline/{oracle_evidence,oracle_verifier}
```

`proofnav/runtime/` 不导入 `proofnav.offline`、oracle provider 或 evaluator。静态 AST 测试逐个
检查 runtime Python 文件；runtime package 公共导出也不包含 controlled/replay 类。

`oracle_verifier.py` 不导入或调用 online verifier。它复制 runtime output 与 hidden truth 后
独立计算 audit outcome，不共享会写回 runtime 的可变状态。

## 2. 两个明确入口

- production：`ProofState`、`EvidenceLedger`、`OnlineVerifier`、`TerminalController`；
- offline/replay：`ControlledProofState`、`OracleEvidenceProvider`、
  `ReplayOnlineVerifier`、`ReplayTerminalController`、`OracleOfflineVerifier`。

两者共享 M1 evidence v1 和相同 proof/certificate/verifier 语义核心，但 admission policy 由类的
代码边界决定，不由配置字符串决定。M2 production admission 是 zero-admission；即使 oracle
记录把 adapter、producer 和 source field 全部改成看似真实的别名，也会被拒绝。

## 3. Truth 流向

Controlled truth 只在 `proofnav/offline/oracle_evidence.py` 被解析。provider 输出只包含 M1
允许的 observation-tethered evidence 字段，并显式标记
`proofnav.controlled-oracle.replay.v1`。隐藏 semantic truth、supported/refuted universe 和
truth artifact digest 不进入 proof snapshot、certificate、online feedback 或 runtime trace。

Offline verifier 的冲突信息只进入测试/审计报告。它不会修改 certificate、proof state、
terminal decision 或下一动作。这个单向边界也意味着 online acceptance 不能被解释为事实正确；
事实正确性必须由 offline audit 与未来 M3 calibration 分别评估。

## 4. M0/M1 与 DUET 保持

固定的六事件 M0 trace slice 不含 GT/evaluator/offline 字段，且继续验证 fused action ID 映射、
travel-only 与 endpoint observation。完整本机 M0 trace 仅通过显式环境变量启用 integration
test。M2 未修改 `map_nav_src/`、原 rollout、原 STOP 逻辑或 legacy prediction evaluator。
