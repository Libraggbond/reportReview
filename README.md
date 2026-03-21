# 报告自动审核工具

报告的自动化审核工具集，基于 Google NotebookLM 实现智能文档审核。

## 项目简介

本项目提供了一套完整的报告自动化审核解决方案：

1. **报告拆分工具** (`split_report.py`) - 将完整的报告按章节自动拆分
2. **自动审核工具** (`notebooklm_auto_review/`) - 基于 Google NotebookLM 进行智能化审核
3. **审核清单** (`checklist.md`) - 预置 11 个大类、16 个问题的专业审核 checklist

## 快速开始

### 方式一：一键自动拆分并审核（推荐）

```bash
cd notebooklm_auto_review

# 登录 Google 账号（首次使用）
python login_notebooklm.py

# 自动拆分报告并审核
python auto_review.py \
    --report /path/to/report.docx \
    --input ./chapters \
    --checklist ../checklist.md \
    --output ./results
```

### 方式二：分步执行

#### 1. 拆分测评报告

```bash
# 交互式选择（默认）
python split_report.py report.docx ./chapters

# 非交互式，使用自动检测的章节配置
python split_report.py report.docx ./chapters --auto
```

#### 2. 安装审核工具环境

```bash
cd notebooklm_auto_review
python setup.py
```

#### 3. 登录 Google 账号

```bash
python login_notebooklm.py
```

#### 4. 运行自动审核

```bash
# 审核全部章节
python auto_review.py --input ./chapters --checklist ../checklist.md

# 只审核指定段落
python auto_review.py -i ./chapters -c ../checklist.md -s 1

# 跳过拆分步骤（如已提前拆分）
python auto_review.py -i ./chapters -c ../checklist.md --skip-split
```

#### 5. 查看结果

审核结果输出到 `notebooklm_auto_review/results/` 目录：
- `review_results_*.json` - 详细 JSON 结果
- `summary_*.md` - Markdown 汇总报告（优化格式）
- `review_*.log` - 运行日志

## 配置说明

编辑 `notebooklm_auto_review/config.yaml`：

```yaml
# Google 账号
# google_account: your-email@gmail.com

# Notebook 配置
notebook_name: "审核"
# notebook_url: "https://notebooklm.google.com/notebook/xxx"

# 代理配置
proxy: "http://127.0.0.1:7890"

# 请求间隔（毫秒）
request_interval: 3000
```

## 目录结构

```
reportReview/
├── README.md                    # 本说明文档
├── checklist.md                 # 审核清单
├── 指引.md                       # 高风险判定参考
├── split_report.py              # 报告拆分脚本
├── notebooklm_auto_review/      # 自动审核工具
│   ├── README.md                # 详细说明
│   ├── auto_review.py           # 主审核脚本
│   ├── notebooklm_client.py     # NotebookLM 客户端
│   ├── checklist_parser.py      # Checklist 解析器
│   ├── login_notebooklm.py      # 登录脚本
│   ├── setup.py                 # 安装脚本
│   ├── config.yaml              # 配置文件
│   └── requirements.txt         # Python 依赖
└── results/                     # 审核结果（本地生成）
```


## 注意事项

- `.auth/` 目录包含 Cookie 认证信息，不会同步到 Git
- 实际的 `.docx` 报告文件不应提交到仓库
- Cookie 有效期约 30 天，过期需重新登录

## License

MIT
