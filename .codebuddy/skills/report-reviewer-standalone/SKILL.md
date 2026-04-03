---
name: report-reviewer-standalone
description: "单 Agent 顺序执行版报告审核技能，不使用子代理或团队。适用于等级保护测评报告等专业文档的审核，支持 checklist 对照检查、错别字检测、结构化审核结果输出。触发词：审核报告, 审查文档, 检查错别字, 审核结果, checklist审核, 报告审核。与 report-reviewer 功能相同，但所有任务由主 Agent 顺序执行，适合不需要并行加速的场景。"
---

# Report Reviewer Skill (单 Agent 顺序执行版)

This skill provides a complete workflow for reviewing and auditing professional
reports. All review tasks are executed **sequentially by the main agent** — no
sub-agents or teams are used. This avoids coordination overhead and simplifies
context management.

## Workflow

### Step 1: Read the Checklist

The checklist file (`checklist.md`) is the authoritative
audit standard and **changes frequently**. Always read it fresh at the start of
each review session. Never rely on cached or previously read content.

- If the user specifies a checklist file path, read that exact file.
- If unspecified, default to `checklist.md` in the project root.

### Step 2: Determine Review Target (Split or Direct)

The review target is a directory containing `.docx` chapter files. There are
two ways to obtain this:

#### 2.1 Case A: User provides a single full report (.docx)

If the user provides a path to a single `.docx` file (a complete report), you
must **first split it** using `split_report.py` before reviewing.

```bash
python split_report.py <input_report.docx> <output_dir> --auto --skip-desensitize
```

- `--auto`: Use auto-detected chapter structure (no interactive prompt).
- `--skip-desensitize`: Do NOT apply desensitization (the review needs original
  text for accurate comparison).

The `<output_dir>` produced by the script becomes the review target directory
for all subsequent steps. Copy `高风险判定指引.md` from the project root to
the output directory if the script doesn't do it automatically.

**IMPORTANT**: After splitting, verify the output directory contains the
expected chapter files using `list_dir` before proceeding.

#### 2.2 Case B: User provides a directory of chapter files

If the user provides a directory path (e.g. `chapters/` or `222_chapters/`),
use it directly as the review target. Skip the splitting step.

Verify the directory contains `.docx` files using `list_dir` before proceeding.

#### 2.3 Determine the final review target directory

After Step 2, the **review target directory** is set. All subsequent steps
(Step 3 onwards) reference files from this directory.

### Step 3: Extract All Chapter Content

**CRITICAL: This step MUST be performed immediately after Step 2.**

Pre-extract all `.docx` chapter files to `.txt` format so the main agent can
read them with `read_file` (binary `.docx` cannot be read directly by LLMs).

```bash
# Create extraction directory
mkdir -p <review_target_dir>/extracted

# Extract all chapter files
for file in <review_target_dir>/*.docx; do
    python <project_root>/extract_docx.py "$file" "<review_target_dir>/extracted/$(basename "$file" .docx).txt"
done
```

After extraction, verify the `extracted/` directory contains all expected
`.txt` files using `ls -la <review_target_dir>/extracted/`.

**Extraction output format** — each `.txt` file follows:

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
  行1: 内容1 | 内容2 | 内容3
...
```

**Skip this step ONLY if** the `extracted/` subdirectory already exists and its
files are up-to-date.

### Step 4: Parse Checklist & Build Review Task List

**CRITICAL: Do NOT list or read all documents at once.** Instead, analyze the
checklist to build a precise review task list that maps each checklist item to
its target documents.

1. **Parse the checklist** (already read in Step 1) to identify:
   - Each checklist item (numbered or titled).
   - The check scope, criteria, and expected judgment.
   - **Target document name(s)** mentioned or implied by each item.

2. **Match document names to files** in the review target directory (determined
   in Step 2).
   - Use `list_dir` to get the actual file list.
   - Fuzzy-match checklist references (e.g. checklist says "测评项目概述",
     match it to `1_测评项目概述.docx`).
   - If a checklist item references a document that doesn't exist, note it as
     a limitation.

3. **Build a review task list** structured as:

```
任务1: [checklist item title]
  ├── 目标文档: [具体文件名, 如 1_测评项目概述.docx]
  ├── 审核要点: [checklist criteria summary]
  └── 状态: 待审核

任务2: [checklist item title]
  ├── 目标文档: [具体文件名]
  ├── 审核要点: [checklist criteria summary]
  └── 状态: 待审核
...
```

4. **Optimize read order**: Reorder tasks so that consecutive tasks targeting
   the same document are grouped together. This minimizes re-reading the same
   file and preserves context.

### Step 5: Execute Review (Sequential, Item-by-Item)

**All review tasks are executed sequentially by the main agent. No sub-agents
or teams are used. Do NOT create teams, spawn sub-agents, or use the `task` tool.**

**All review activities must strictly follow the checklist (`checklist.md`).**
Do not apply review criteria beyond what the checklist specifies.

**CRITICAL: Use the LLM (large language model) to perform the review directly.**
Scripts are ONLY allowed for extracting/reading content from `.docx` files
(Step 3). The actual analysis, judgment, and conclusion MUST be done by the
LLM reading and reasoning over the content.

#### 5.1 Review Loop

Iterate through the review task list (built in Step 4). For each task:

1. **Read the target document** from `extracted/` subdirectory:
   ```
   read_file(filePath: "<review_target_dir>/extracted/<document_name>.txt")
   ```
   - If the document was already read for a previous task (same file, still in
     context), reuse the content — do NOT re-read.
   - For large files (1000+ lines), use `offset` and `limit` to read only
     the sections relevant to the current checklist item.

2. **Focus only on the current checklist item's criteria.** Do not attempt to
   review other checklist items at the same time.

3. **Read the extracted content carefully** and apply the checklist criteria.

4. **Record findings** using this format:
   ```
   问题X：[checklist item title]
   所在文件：[具体文件名，如 3_单项测评结果分析.docx]
   所在位置：[段落号/表格号/行号等具体位置信息]
   问题点：[specific issues found in the document, with location references]
   审核结论：[通过 / 不通过 / 部分通过（附详细说明）]
   ```

5. **After recording findings**, mark the task as done and move to the next.

#### 5.2 Context Management (Critical for Single-Agent Mode)

Since all tasks run in a single context window, strict context management is
essential:

- **One document at a time**: Never load more than one document's full content
  at a time. If a checklist item requires checking multiple documents, process
  them sequentially — finish reviewing document A, then read and review document B.

- **Checkpoint every 2-3 items**: After completing 2-3 checklist items,
  **immediately append findings to the output file**. Do NOT wait until all
  items are done. This prevents losing results if context is truncated.
  Pattern:
  1. Complete items 1-3, write partial results to the output markdown file.
  2. Complete items 4-6, append to the same file.
  3. Repeat until all items are done.

- **Large document handling**: For documents with 1000+ lines, do NOT read the
  entire file into context. Use `read_file` with `offset` and `limit` to read
  only the sections relevant to the current checklist item.

- **Re-read when needed**: If you need to refer to a document that was read
  earlier but is no longer in context, re-read only the relevant sections
  using offset/limit. Do not re-read the entire file.

#### 5.3 Strict Compliance Rules

- **Only check what the checklist specifies.** Do not add ad-hoc review items.
- **Only judge by the checklist's criteria.** Do not substitute personal judgment
  for the checklist's standards.
- **If the checklist is updated**, the review scope and criteria change
  accordingly. Always re-read the checklist before each review session.
- **If a checklist item cannot be checked** due to missing content or
  inaccessible files, clearly state the limitation in the output.

### Step 6: Output Results

Write review results to a markdown file in the **review target directory** (the
directory determined in Step 2). Structure:

```markdown
# 审核结果

## 审核依据
- Checklist 文件路径：[e.g. checklist.md]
- Checklist 读取时间：[timestamp]

## 审核范围
- 审核文档列表

## 审核汇总
| 类别 | 审核内容 | 问题数 | 结论 |
|------|---------|-------|------|
| 类别X | [content] | N | 通过/不通过/部分通过 |
...

## 发现的问题（按严重程度排序）

### 高严重程度
#### 1. [问题描述标题]
- **对应Checklist：** 类别X-问题Y
- **所在文件：** [具体文件名，可多个]
- **所在位置：** [段落号/表格号/行号]
- **具体问题：** [详细描述]

### 中严重程度
...

### 低严重程度
...

## 通过的审核项
| 类别 | 审核内容 | 通过原因 |
|------|---------|---------|
...
```

**Key output rules:**

1. **Every discovered problem MUST include "所在文件"** (source file name) and
   "所在位置" (specific location like paragraph number, table number, or row
   number). Never describe a problem without specifying exactly which file and
   where in that file it exists.
2. Problems are sorted by severity: **高** (critical factual errors), **中**
   (incorrect wording affecting meaning), **低** (formatting/punctuation
   inconsistencies). Severity levels follow the checklist if defined; otherwise
   use the defaults above.
3. The summary table at the end lists all **passed** checklist items for
   completeness, so the reviewer can see what was checked and confirmed OK.
4. If a problem spans multiple files, list ALL affected files.
5. Use the exact original file names (e.g., `3_单项测评结果分析.docx`), not
   abbreviations.

### Step 7: Cleanup Temporary Files

**After the review is fully complete and results have been written**, clean up
all temporary files created during the review process.

1. **Ask the user** if they want to keep the `extracted/` directory.
2. If not, delete it:
   ```bash
   rm -rf <review_target_dir>/extracted/
   ```
3. **Always preserve** the final review result file (e.g. `审核结果.md`).

## Notes

- Always use the user's language (Chinese) for all output and communication.
- When reviewing, consider the document type: 等级保护测评 reports have
  specific terminology standards. Use established terms (e.g. "敏感信息" not
  "私密信息", "泄露" not "泄漏").
- Report files are stored in the `chapters/` directory as `.docx` files.
- The checklist is a living document that gets updated regularly; always read
  the latest version before each review.
- **This skill uses single-agent sequential execution only.** Do NOT create
  teams, sub-agents, or use the `task` tool to spawn parallel workers. All
  review work is done by the main agent reading one document at a time.
