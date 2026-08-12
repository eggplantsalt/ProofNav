# ProofNav M2 CPU Falsification Report

> 日期：2026-08-12（UTC）  
> 性质：micro logic falsification；不是形式化证明、模型实验或 benchmark

## 1. 已执行检查

- M1 conformance：27/27 CPU tests；strict GT/unknown-field rejection、action mapping、legacy
  output 和固定 M0 trace slice 均通过；
- M2 unit/metamorphic：32 tests；
- 四类 false premise 各自运行完整 refutation acceptance、缺 cover rejection/final
  UNRESOLVED 和 M1 single-premise pair validator；
- 两 hypothesis、每个 obligation 取 open/support/refute/conflict 的 16 种状态穷举；
- production/oracle alias、runtime import graph、offline verifier reverse dependency 静态检查；
- 固定 M0 trace 的 CPU replay/action mapping smoke；不加载 checkpoint 或模型。

实际命令与结果：

```bash
python -m py_compile proofnav/*.py proofnav/runtime/*.py proofnav/offline/*.py \
  tests/m1/*.py tests/m2/*.py tests/integration/*.py
# exit 0

python -m unittest discover -s tests/m1 -p 'test_*.py' -v
# Ran 27 tests ... OK

python -m unittest discover -s tests/m2 -p 'test_*.py' -v
# Ran 32 tests ... OK

python -m unittest discover -s tests -p 'test_*.py' -v
# Ran 60 tests ... OK (skipped=1; explicit local integration is default-off)

PROOFNAV_RUN_LOCAL_M0_INTEGRATION=1 \
PROOFNAV_M0_TRACE_PATH=.m0-results/traces/dynamic_runtime_trace.jsonl \
python -m unittest tests.integration.test_local_m0_trace -v
# Ran 1 test ... OK
```

## 2. Cheapest-killer 结果

| Killer | 预期 | 结果 |
|---|---|---|
| 删除 positive necessary support | FOUND 失效 | 通过：旧证书 stale，新构造 UNRESOLVED |
| 增加未覆盖 hypothesis | NOT_FOUND 失效 | 通过：scope/digest 与 coverage 拒绝 |
| open frontier | 阻止 NOT_FOUND | 通过 |
| evidence 排列 | 证书/verifier 稳定 | 通过：semantic digest 与证书字节相同 |
| 无关 optional evidence | 合法 verdict 不变 | 通过 |
| conflict | 不任选 FOUND/NOT_FOUND | 通过 |
| 16 种小状态 | 不同时接受正/负 | 通过；最多一个 verdict accepted |
| DUET STOP/no-vp/max/budget | 不制造 NOT_FOUND | 通过：continue 或 forced UNRESOLVED |
| oracle 改名成 perception | production 仍拒绝 | 通过：zero-admission |

## 3. 负面证据与 failure-to-design loop

### 最小反例

隐藏事实为 FOUND，但 controlled predicate output 错误地产生完整 refutation evidence。结构上完整的
NOT_FOUND certificate 被 replay online verifier 接受；独立 offline verifier 返回
`FALSE_ACCEPT`、`online_offline_conflict=true`、`certificate_accepted_for_audit=false` 和
`audit_disposition=UNRESOLVED`。

### 失败定位

这不是 coverage/verifier 实现错误，而是**假设/claim 层**反例：只读 agent-visible evidence 的
online verifier 无法从形式结构推出 predicate 的世界事实正确性。

### 修复候选

1. online 读取 evaluator truth：逻辑上能拦截，但直接破坏研究的 truth firewall，淘汰；
2. 仅增加 adapter 名称/配置 allowlist：alias micro-test 可绕过，淘汰；
3. M2 将 soundness 明确限定为 validated-and-correct evidence 条件，生产 evidence zero-admission，
   offline 独立审计所有 factual conflict：当前采用；
4. 多 adapter 冗余、置信度/依赖组合与 calibration：可能降低而不能逻辑消除相关错误，保留为
   M3 falsification 对象，不在 M2 提前实现。

### 结论

M2 的 certificate logic 与 terminal gate 在 controlled-correct evidence 假设下成立；**“online
acceptance 等于事实正确”这一无条件 claim 被反例否定并明确退休。** 当前修复保住 M2 的逻辑
职责和 firewall，但真实 factual soundness 仍阻塞在 M3 perception/calibration，而不是被单元
测试宣称解决。

## 4. 尚未验证

- 没有真实 predicate model、置信度或风险 calibration；
- 没有 DUET 正式闭环接线、re-ranking、训练或 GPU；
- 没有正式 paired REVERIE 生成或 benchmark；
- M1 risk claim 在 M2 是 controlled fixture 输入，测试只验证预算/一致性 gate，不证明数值有效；
- offline conflict 不回写 runtime；审计降级不能补救一次历史 online action。
