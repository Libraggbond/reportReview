# notebooklm_auto_review 程序结构

## 目录结构

```
notebooklm_auto_review/
├── auto_review.py          # 主程序入口（494 行）
├── notebooklm_client.py    # NotebookLM 客户端（962 行）
├── checklist_parser.py     # Checklist 解析器（262 行）
├── login_notebooklm.py     # 登录脚本（72 行）
├── config.yaml             # 配置文件
├── requirements.txt        # Python 依赖
├── PROGRESS.md            # 测试进度记录
├── CONTEXT.md             # 本文档 - 程序结构说明
├── README.md              # 使用文档
├── .auth/                 # Cookie 存储目录
│   └── cookies.json       # 登录 Cookie
├── results/               # 输出结果目录
└── chapters/              # 待审核文档（父目录）
```

## 核心模块

### 1. auto_review.py (主程序)

**核心函数**:
- `main()` - 主流程（L253-428）
- `review_section()` - 审核单个段落（L136-250）
- `upload_documents()` - 批量上传文档（L91-133）
- `generate_summary_report()` - 生成汇总报告（L430-491）

**执行流程**:
```
1. 加载 checklist → 2. 启动浏览器 → 3. 登录
→ 4. 打开/创建 Notebook → 5. 上传所有文档
→ 6. 逐段审核 (review_section) → 7. 生成报告
```

**关键逻辑** (L183-203):
```python
# 对每个问题：
question_docs = extract_documents_from_question(question.content)  # 从问题提取
relevant_docs = [d for d in question_docs if d in uploaded_docs]  # 过滤
if not relevant_docs:
    relevant_docs = uploaded_docs  # fallback: 使用全部文档
```

### 2. notebooklm_client.py (浏览器自动化)

**核心类**: `NotebookLMClient`

**关键方法**:
| 方法 | 功能 | 行号 |
|------|------|------|
| `launch_browser()` | 启动 Chromium | L63 |
| `login()` | 登录 NotebookLM | L138 |
| `upload_documents_batch()` | 批量上传文档 | L270 |
| `select_sources()` | 选择参考文档 | L801 |
| `ask_question()` | 提问并获取回答 | L437 |
| `wait_for_batch_upload_complete()` | 等待上传完成 | L335 |

**重要修复** (L824):
```javascript
// 支持 .md 和 .txt 文件的选中/取消选中
if (text && (text.includes('.docx') || text.includes('.pdf') ||
             text.includes('.md') || text.includes('.txt')) && checkbox)
```

### 3. checklist_parser.py (解析器)

**数据结构**:
- `Question` - 单个问题
- `ChecklistSection` - 段落
- `Checklist` - 完整清单

**核心函数**:
- `parse_checklist()` - 解析 markdown 文件 (L58)
- `extract_documents_from_question()` - 从问题提取文档名 (L156)
  ```python
  pattern = r"[\'\"\u2018\u2019]([^\u2018\u2019\'\"]+?\.(?:docx|pdf|txt|md|doc))[\u2018\u2019\'\"]"
  ```

## 配置文件 (config.yaml)

```yaml
output_dir: ./results
notebook_name: "等级测评报告审核"
notebook_url: "https://notebooklm.google.com/notebook/8707e98c-4ab9-452b-a719-b22ffb423452"
request_interval: 3000  # 请求间隔 (毫秒)
proxy: "http://127.0.0.1:7890"
```

## 命令行用法

```bash
# 登录
python3 login_notebooklm.py

# 测试单个段落
python3 auto_review.py -s 1 -i ../chapters -c ../checklist.md

# 测试全部段落
python3 auto_review.py -i ../chapters -c ../checklist.md
```

## 已知问题/修复记录

| 问题 | 状态 | 修复位置 |
|------|------|----------|
| .md 文件不会被取消选中 | ✅ 已修复 | notebooklm_client.py:824 |
| 上传等待死循环 | ✅ 已修复 | notebooklm_client.py:335 |

## 快速定位

- 查看提问逻辑：`auto_review.py:205-210`
- 查看文档选择逻辑：`notebooklm_client.py:801-868`
- 查看文档提取正则：`checklist_parser.py:170`
