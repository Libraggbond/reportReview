# 报告自动审核工具

报告自动化审核工具集，基于 Claude Code Skills 实现智能文档审核。

## 项目简介

本项目提供了一套完整的报告自动化审核解决方案：

1. **报告拆分工具** (`split_report.py`) - 将完整的报告按章节自动拆分
2. **审核 Skills** (`.codebuddy/skills/`) - 基于 Claude Code 的智能审核技能
3. **审核清单** (`checklist.md`) - 预置专业审核 checklist

## 快速开始

### 方式一：使用 Claude Code Skills 审核（推荐）

本项目提供两个审核 Skills，在 Claude Code 中直接调用：

#### 1. report-reviewer（并行审核）

支持子代理并行审核，适合大规模审核任务：

```
审核报告 /path/to/report.docx
```

或指定已拆分的目录：

```
审核报告 /path/to/chapters/
```

#### 2. report-reviewer-standalone（单 Agent 顺序审核）

所有任务由主 Agent 顺序执行，适合不需要并行加速的场景：

```
审核报告 /path/to/report.docx
```

触发词：`审核报告`、`审查文档`、`检查错别字`、`checklist审核`

### 方式二：命令行拆分 + 手动审核

#### 1. 拆分测评报告

```bash
# 自动拆分（非交互式）
python split_report.py report.docx ./chapters --auto --skip-desensitize

# 交互式选择章节配置
python split_report.py report.docx ./chapters
```

拆分后自动复制以下文件到输出目录：
- `高风险判定指引.md`
- `beian.png`

#### 2. 提取章节内容

```bash
# 创建提取目录
mkdir -p ./chapters/extracted

# 提取所有章节文件
for file in ./chapters/*.docx; do
    python extract_docx.py "$file" "./chapters/extracted/$(basename "$file" .docx).txt"
done
```

提取后的 `.txt` 文件格式：
```
================================================================================
文档: [文件名.docx]
================================================================================

【段落内容】
总段落数: N

[P0] 第一段内容
[P1] 第二段内容
...

【表格内容】
总表格数: M

--- 表格 1 (X行 x Y列) ---
  行0: 内容1 | 内容2 | 内容3
...
```

#### 3. 使用 Claude Code 审核

在 Claude Code 中，切换到拆分目录并执行审核：

```
审核报告 ./chapters/
```

## Skill 审核流程

两个 Skill 执行相同的工作流程：

| 步骤 | 说明 |
|------|------|
| Step 1 | 读取 checklist.md（每次重新读取，不使用缓存） |
| Step 2 | 确定审核目标（拆分报告或使用现有目录） |
| Step 3 | 预提取所有章节内容到 extracted/ 目录 |
| Step 4 | 解析 checklist，构建审核任务列表 |
| Step 5 | 逐项执行审核，按 checklist 标准判断 |
| Step 6 | 输出审核结果（Markdown 格式） |
| Step 7 | 清理临时文件 |

## 审核结果格式

审核结果输出到审核目标目录的 `审核结果.md`：

```markdown
# 审核结果

## 审核依据
- Checklist 文件路径：checklist.md
- Checklist 读取时间：[timestamp]

## 审核汇总
| 类别 | 审核内容 | 问题数 | 结论 |
|------|---------|-------|------|

## 发现的问题（按严重程度排序）

### 高严重程度
#### 1. [问题描述标题]
- **对应Checklist：** 类别X-问题Y
- **所在文件：** [具体文件名]
- **所在位置：** [段落号/表格号/行号]
- **具体问题：** [详细描述]

### 中严重程度
...

### 低严重程度
...

## 通过的审核项
| 类别 | 审核内容 | 通过原因 |
|------|---------|---------|
```

## 目录结构

```
reportReview/
├── README.md                    # 本说明文档
├── checklist.md                 # 审核清单
├── 高风险判定指引.md            # 高风险判定参考
├── beian.png                    # 备案相关图片
├── split_report.py              # 报告拆分脚本
├── extract_docx.py              # 文档内容提取脚本
├── .codebuddy/
│   └── skills/
│       ├── report-reviewer/             # 并行审核 Skill
│       │   └── SKILL.md
│       └── report-reviewer-standalone/  # 单 Agent 审核 Skill
│           └── SKILL.md
```

## 两种 Skill 对比

| 特性 | report-reviewer | report-reviewer-standalone |
|------|-----------------|---------------------------|
| 执行模式 | 支持并行子代理 | 单 Agent 顺序执行 |
| 适用场景 | 大规模审核（10+ checklist 项） | 小规模审核或简单场景 |
| 协调开销 | 有子代理协调开销 | 无协调开销 |
| 上下文管理 | 子代理独立上下文 | 主 Agent 统一管理 |

## 注意事项

- `.auth/` 目录包含 Cookie 认证信息，不会同步到 Git
- 实际的 `.docx` 报告文件不应提交到仓库
- checklist 是动态更新的文档，每次审核前重新读取
- 审核严格遵循 checklist 标准，不添加额外审核项

## License

MIT