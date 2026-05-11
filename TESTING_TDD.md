# TDD 开发流程（强制）

本项目默认执行 **测试先行**：

1. **改业务逻辑前先补测试**：先写失败测试，再改实现让测试通过。
2. **修 Bug 先写复现测试**：先在 `tests/` 中复现，再修复。
3. **重构不改行为**：重构前后测试集必须保持通过。
4. **Agent 生成代码后自动跑测试**：任何由 Agent 生成并落盘的代码，提交前必须执行测试（推荐 `make tdd-check` 或 `python -m pytest -q --maxfail=1`）。

## 推荐命令

```bash
# 快速回归（推荐提交前）
make tdd-check
# 或
python -m pytest -q --maxfail=1

# 全量测试
make test
# 或
python -m pytest -q
```

## 提交门禁建议

- 提交前至少运行一次 `make tdd-check`（或等价 `python -m pytest -q --maxfail=1`）。
- 若新增功能，至少新增一个失败→修复→通过的测试案例（可在 PR 描述注明）。
