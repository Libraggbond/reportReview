---
name: report-reviewer
description: "This skill should be used when the user needs to review and audit documents, especially 等级保护测评报告 (classified protection assessment reports) or similar professional technical reports. It handles reading docx files, checking against checklists, detecting typos/errors, and producing structured audit results. Trigger phrases include 审核报告, 审查文档, 检查错别字, 审核结果, checklist审核, 报告审核, or any request to review/audit report documents in the chapters directory."
---

# Report Reviewer Skill

This skill provides a complete workflow for reviewing and auditing professional
reports, with built-in safeguards against content truncation during long document
reading.

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

### Step 2.5: Extract All Chapter Content (Pre-Extraction)

**CRITICAL: This step MUST be performed immediately after Step 2 (splitting or
identifying the target directory). Pre-extraction is REQUIRED for efficient
parallel review.**

#### 2.5.1 Why Pre-Extract?

Sub-agents (code-explorer) **CANNOT directly read .docx binary files**. If each
sub-agent has to extract files on-demand, it creates significant overhead and
reduces efficiency. Pre-extracting all chapter content upfront solves this problem:

- Sub-agents can directly read `.txt` files using `read_file` tool
- No need for each sub-agent to run extraction scripts
- Faster parallel review execution
- Consistent extraction format across all reviewers

#### 2.5.2 Extraction Process

Create a subdirectory called `extracted/` within the review target directory and
extract all `.docx` chapter files to `.txt` format:

```bash
# Create extraction directory
mkdir -p <review_target_dir>/extracted

# Extract all chapter files
for file in <review_target_dir>/*.docx; do
    python <project_root>/extract_docx.py "$file" "<review_target_dir>/extracted/$(basename "$file" .docx).txt"
done
```

**Example:**
```bash
mkdir -p /path/to/222_chapters/extracted
for file in /path/to/222_chapters/*.docx; do
    python /path/to/reportReview/extract_docx.py "$file" "/path/to/222_chapters/extracted/$(basename "$file" .docx).txt"
done
```

#### 2.5.3 Verify Extraction

After extraction, verify the `extracted/` directory contains all expected `.txt` files:

```bash
ls -la <review_target_dir>/extracted/
```

Expected output: For each `.docx` file in the target directory, there should be
a corresponding `.txt` file with the same base name.

#### 2.5.4 Extraction Output Format

Each extracted `.txt` file follows this standardized format:

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

This format preserves:
- Paragraph numbering (P0, P1, P2...)
- Table structure with row indices
- Clear section markers for easy navigation

#### 2.5.5 When NOT to Pre-Extract

Skip this step ONLY if:
- The user provides a directory that already contains `extracted/` subdirectory
- Previous extraction files exist and are up-to-date

In these cases, verify the existing extraction files match the `.docx` files before
proceeding.

### Step 3: Parse Checklist & Build Review Task List

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

4. **Deduplicate reads**: If multiple checklist items target the same document,
   note it so the document is extracted only once but reviewed against all
   relevant checklist items.

### Step 4: Read Document Content (From Pre-Extracted Files)

**CRITICAL: All chapter content was pre-extracted in Step 2.5. Read from `.txt`
files in the `extracted/` subdirectory.**

**✅ CORRECT PATTERN (Using Pre-Extracted Files):**

For each checklist item (in order):
1. Identify which document(s) this item needs.
2. Check if that document's content is already in your context (from a previous
   item). If yes, reuse it. If no, read the `.txt` file NOW from the `extracted/`
   directory.
3. Perform the review against this checklist item.
4. Move to the next checklist item.

**⛔ PROHIBITED ANTI-PATTERNS (must NOT do):**

1. **Do NOT read .docx binary files directly** — they cannot be parsed by LLMs.
2. **Do NOT run extraction scripts during review** — files are already extracted.
3. **Do NOT batch-read multiple documents at once** — read one at a time to avoid
   context overflow.

#### 4.0 When to Read a Document

- Read documents from the `extracted/` subdirectory (created in Step 2.5).
- Only read a document when you are about to review a checklist item that
  targets it.
- If the document has already been read for a previous checklist item, reuse
  the content (do not re-read unless you suspect issues).
- If a checklist item targets multiple documents, read them sequentially — do
  not read multiple documents in parallel.

#### 4.1 Reading Pre-Extracted Text Files

Use `read_file` tool to read the `.txt` files:

```
read_file(filePath: "<review_target_dir>/extracted/<document_name>.txt")
```

**Example:**
```
read_file(filePath: "/path/to/222_chapters/extracted/3_单项测评结果分析.txt")
```

The extracted `.txt` files contain:
- Paragraph content with indices: `[P0]`, `[P1]`, `[P2]`...
- Table content with row indices: `行0`, `行1`, `行2`...
- Clear section markers: `【段落内容】`, `【表格内容】`

#### 4.2 Large Document Handling

For very large extracted files (e.g., `附录_单项测评结果记录.txt` with ~200K tokens):

- Use `read_file` with `offset` and `limit` parameters to read sections
- Read only the sections relevant to the current checklist item
- Example: Read paragraphs 100-150 for a specific table check

```
read_file(
  filePath: "/path/to/extracted/附录_单项测评结果记录.txt",
  offset: 500,  // Start from line 500
  limit: 200    // Read 200 lines
)
```

#### 4.3 Validate Completeness

When reading large files in sections:
1. Note the total line count before reading
2. After reading a section, verify you got the expected content
3. If content seems incomplete, read the next section

#### 4.4 Context Management

- **Avoid context overflow**: Never load more than one document's full content
  at a time into your context.
- **Reuse content**: If two consecutive checklist items target the same document,
  reuse the already-read content instead of re-reading.
- **Checkpoint results**: After every 2-3 checklist items, write partial results
  to the output file to prevent loss if context is truncated.

### Step 5: Perform Review (Item-by-Item, Document-on-Demand)

**All review activities must strictly follow the checklist (`checklist.md`).**
Do not apply review criteria beyond what the checklist specifies. The checklist
is the sole authoritative standard for determining what to check and how to
judge.

**CRITICAL: Use the LLM (large language model) to perform the review directly.**
Scripts are ONLY allowed for extracting/reading content from `.docx` files
(Steps 1-3). The actual analysis, judgment, and conclusion MUST be done by the
LLM reading and reasoning over the content. Do NOT write scripts to automate
the review logic (e.g. do not write scripts to match patterns, compare strings,
or check compliance). The LLM must read the extracted text and apply the
checklist criteria using its own understanding and judgment.

#### 5.0 Parallel Review Strategy (When to Use Sub-Agents)

When the checklist has many items (e.g. 10+), you MAY split the review across
parallel sub-agents for efficiency. However, you MUST follow these rules:

**✅ NEW: Direct Text File Reading (After Pre-Extraction)**

Since all chapter content was pre-extracted in Step 2.5, sub-agents can now
directly read the extracted `.txt` files without running extraction scripts.

**Sub-agent text file reading protocol:**

1. **Read**: Use `read_file` to read the pre-extracted `.txt` file from the
   `extracted/` subdirectory:
   ```
   read_file: <review_target_dir>/extracted/<document_name>.txt
   ```
2. **Review**: Analyze the extracted text content and perform the review.

**This is much simpler than the old extraction protocol!** No need to run
`execute_command` for extraction anymore.

**What to send to each sub-agent:**
- The specific checklist item(s) assigned to it (with full criteria text).
- The target document NAME(S) for each item (e.g., `3_单项测评结果分析.docx`).
- **The absolute path to the `extracted/` directory** (containing `.txt` files).
- **The simple reading protocol above** (just read the `.txt` file directly).
- Instructions on where to write results (e.g. `/tmp/review_result_partN.md`).

**What NOT to send to each sub-agent:**
- ⛔ Pre-extracted file contents (do NOT paste document text into prompts).
- ⛔ File content from your own context (let sub-agent read files itself).
- ⛔ All document names at once (only send the names relevant to that agent's items).
- ⛔ Instructions to run extraction scripts (files are already extracted).

**Sub-agent responsibility:**
Each sub-agent must:
1. Read the pre-extracted `.txt` files for its assigned documents
2. Review each assigned checklist item against the criteria
3. Manage its own context (read files one at a time)
4. Write results to the specified output file

**Example of correct sub-agent launch:**
```
Task for sub-agent:
- Assigned items: 类别7-问题1, 类别7-问题2, 类别7-问题3
- Target documents for these items: 3_单项测评结果分析.docx, 附录_漏洞扫描结果记录.docx, 2_被测对象描述.docx
- Extracted files directory: /path/to/222_chapters/extracted/

✅ SIMPLE: Just read the pre-extracted .txt files directly:
- For 3_单项测评结果分析.docx → read_file: /path/to/222_chapters/extracted/3_单项测评结果分析.txt
- For 附录_漏洞扫描结果记录.docx → read_file: /path/to/222_chapters/extracted/附录_漏洞扫描结果记录.txt
- For 2_被测对象描述.docx → read_file: /path/to/222_chapters/extracted/2_被测对象描述.txt

Do NOT try to read .docx files directly (they are binary).
Do NOT run extraction scripts (files are already extracted in Step 2.5).
Read each file only when you need it for a specific checklist item.

- Review each assigned item against the checklist criteria.
- Write results to /tmp/review_result_part2.md
```

**⛔ OLD PROTOCOL (NO LONGER USED):**

The previous 3-step extraction protocol (extract → read → review) is now
obsolete. All files are pre-extracted in Step 2.5. Sub-agents should only
read `.txt` files directly.

#### 5.1 Review Loop: One Checklist Item at a Time

Iterate through the review task list (built in Step 2). For each task:

1. **Check if target document content is already in context** (extracted for a
   previous checklist item). If yes, skip extraction; if no, go to Step 3 to
   extract it now.
2. **Focus only on the current checklist item's criteria.** Do not attempt to
   review other checklist items at the same time, even if the same document is
   open. This ensures thoroughness and prevents missed issues caused by context
   overload.
3. **Read the extracted content carefully** and apply the checklist criteria.
4. **Record findings** using this format:

```
问题X：[checklist item title]
所在文件：[具体文件名，如 3_单项测评结果分析.docx]
所在位置：[段落号/表格号/行号等具体位置信息]
问题点：[specific issues found in the document, with location references]
审核结论：[通过 / 不通过 / 部分通过（附详细说明）]
```

5. **After recording findings for the current item**, mark the task as done
   and move to the next checklist item.

#### 5.2 Memory & Context Management

- **Avoid context overflow**: Never load more than one document's full content
  at a time. If a checklist item requires checking multiple documents, process
  them sequentially — finish reviewing document A against the item, then read
  and review document B.
- **Reuse extracted content**: If two consecutive checklist items target the
  same document, reuse the already-extracted content instead of re-extracting.
  However, if the document is very large and you're running low on context,
  re-extract only the relevant sections.
- **Checkpoint periodically and persist results**: After every 2-3 checklist
  items, **append findings to the output file immediately** (do not wait until
  all items are done). This prevents losing results if context is truncated.
  Use this pattern:
  1. After completing checklist items 1-3, write partial results to the output
     markdown file.
  2. Continue with items 4-6, then append to the same file.
  3. Repeat until all items are done.
- **Large document handling**: For documents with 1000+ lines, do NOT read the
  entire file into context. Instead, use `read_file` with `offset` and `limit`
  parameters to read sections relevant to the current checklist item (e.g.
  specific tables or paragraphs).

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
directory determined in Step 2). If the report was split from a single file,
save the result in the split output directory alongside the chapter files.
Structure:

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

## Notes

- Always use the user's language (Chinese) for all output and communication.
- When reviewing, consider the document type: 等级保护测评 reports have
  specific terminology standards. Use established terms (e.g. "敏感信息" not
  "私密信息", "泄露" not "泄漏").
- Report files are stored in the `chapters/` directory as `.docx` files.
- The checklist is a living document that gets updated regularly; always read
  the latest version before each review.

### Step 7: Cleanup Temporary Files

**After the review is fully complete and results have been written**, clean up
all temporary files created during the review process.

#### 7.1 Files to Clean Up

During the review, these temporary files may be created:

1. **Pre-extracted text files**: `<review_target_dir>/extracted/*.txt` (from Step 2.5)
2. **Partial result files**: `/tmp/review_result_part*.md` (from parallel sub-agents)
3. **Any other temp files** created during the review process

#### 7.2 Cleanup Rules

- **Only clean up after all review work is done** — do NOT delete temp files
  while sub-agents are still running or while the final report is being assembled.
- **Do NOT delete the final output file** (e.g. `审核结果.md` in the target
  directory). This is the deliverable, not a temp file.
- **Clean up extracted directory**: After review, ask user if they want to keep
  the `extracted/` directory. If not, delete it:
  ```bash
  rm -rf <review_target_dir>/extracted/
  ```
- **Clean up partial result files**: Use `delete_file` tool or shell command:
  ```bash
  rm -f /tmp/review_result_part*.md
  ```
- **Confirm cleanup**: After deletion, verify files are gone.

#### 7.3 When Using Parallel Sub-Agents

If parallel sub-agents were used (Step 5.0):
1. Wait until ALL sub-agents have completed and reported results.
2. Merge partial results into the final output file.
3. Then clean up all temp files (both main agent's and sub-agents').

#### 7.4 When Using Split Report (Step 2)

If the report was split from a single file in Step 2:
1. The split output directory contains:
   - Chapter `.docx` files
   - `extracted/` subdirectory with `.txt` files
   - Final review result file (e.g., `审核结果.md`)
2. Ask the user what to keep:
   - **Option A**: Keep everything (for future reference)
   - **Option B**: Keep only `.docx` files and `审核结果.md`, delete `extracted/`
   - **Option C**: Keep only `审核结果.md`, delete everything else
3. If user wants to delete, use appropriate `rm` commands.
4. **Always preserve** the final review result file (`审核结果.md`).