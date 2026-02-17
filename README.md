# cursor-claude-skill-bridge

Cursor 与 Claude Code (Codex) 之间的 Skill 格式互转工具。

## 背景

[Cursor](https://cursor.com/) 和 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 都支持 **Skills** 机制——通过 `SKILL.md` 文件为 AI Agent 提供领域知识、专业工作流和工具集成。两者格式非常相似（都使用 YAML 前置数据 + Markdown），但在目录结构和文件组织上存在差异。

本工具可以在两种格式之间进行自动转换，让你在一个平台编写的 Skill 能够快速迁移到另一个平台使用。

## 格式对比

| 特性 | Claude Code Skill | Cursor Skill |
|------|------------------|--------------|
| 存储位置 | `~/.claude/skills/` | `~/.cursor/skills/` (个人) 或 `.cursor/skills/` (项目) |
| 入口文件 | `SKILL.md` | `SKILL.md` |
| 前置数据 | `name` + `description` | `name` + `description` |
| 脚本目录 | `scripts/` (推荐)，也支持同级目录 | `scripts/` (推荐) |
| 参考文档 | `references/` 子目录 | 与 SKILL.md 同级 (如 `reference.md`) |
| 资源文件 | `assets/` 子目录 | 灵活组织 |
| 名称限制 | 小写字母、数字、连字符 | 最长 64 字符，小写字母、数字、连字符 |
| 描述限制 | 无硬性限制 | 最长 1024 字符 |
| 文件长度建议 | SKILL.md < 500 行 | SKILL.md < 500 行 |

## 转换逻辑

### Claude → Cursor

- 同级的脚本文件（`.py`, `.sh` 等）→ 移入 `scripts/` 子目录
- `references/` 下的文件 → 提升到与 `SKILL.md` 同级
- 前置数据仅保留 `name` 和 `description`
- 自动更新 `SKILL.md` 中的文件引用路径

### Cursor → Claude

- 同级的参考文档（`.md` 等）→ 移入 `references/` 子目录
- 同级的脚本文件 → 移入 `scripts/` 子目录
- 同级的资源文件 → 移入 `assets/` 子目录
- 前置数据仅保留 `name` 和 `description`
- 自动更新 `SKILL.md` 中的文件引用路径

## 安装

无需安装额外依赖，仅需 Python 3.9+：

```bash
git clone https://github.com/honeywellwenjie/cursor-claude-skill-bridge.git
cd cursor-claude-skill-bridge
```

## 使用方法

```bash
python convert.py <方向> <源目录> [-o <输出目录>] [--dry-run]
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `方向` | `claude2cursor` / `cursor2claude` / `auto`（自动检测） |
| `源目录` | 源 skill 的目录路径 |
| `-o, --output` | 输出目录路径（默认：当前目录下以 skill 名称命名） |
| `--dry-run` | 预览模式：仅显示将执行的操作，不写入文件 |

### 示例

```bash
# Claude skill → Cursor skill
python convert.py claude2cursor ~/.claude/skills/my-skill -o ~/.cursor/skills/my-skill

# Cursor skill → Claude skill
python convert.py cursor2claude ~/.cursor/skills/my-skill -o ~/.claude/skills/my-skill

# 自动检测方向（根据源路径判断）
python convert.py auto ~/.claude/skills/my-skill -o ./output/my-skill

# 预览模式（不实际写入文件）
python convert.py claude2cursor ~/.claude/skills/my-skill -o ./out --dry-run
```

### 实际使用示例

将本仓库 `claude-skills/` 示例转换为 Cursor 格式：

```bash
python convert.py claude2cursor claude-skills/analyzing-financial-statements \
  -o cursor-skills/analyzing-financial-statements
```

## 项目结构

```
cursor-claude-skill-bridge/
├── convert.py                # 核心转换工具
├── README.md                 # 本文件
├── claude-skills/            # Claude Code skill 示例
│   └── analyzing-financial-statements/
│       ├── SKILL.md
│       ├── calculate_ratios.py
│       └── interpret_ratios.py
└── cursor-skills/            # Cursor skill 示例（转换后输出）
```

## 注意事项

- 转换仅调整目录结构和文件路径引用，**不修改 Skill 的核心指令内容**
- 两种格式的 AI Agent 工具 API 不同（如 Cursor 使用 `Read`/`Write`/`Shell`，Claude Code 使用 `Bash`/`Read`/`Write`/`Edit`），涉及特定工具调用的指令可能需要手动调整
- 建议先使用 `--dry-run` 预览转换结果，再执行实际转换
- 输出目录非空时会提示确认

## License

MIT
