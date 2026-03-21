# 等级测评报告自动审核工具

网络安全等级保护测评报告的自动化审核工具集，基于 Google NotebookLM 实现智能文档审核。

## 项目简介

本项目提供了一套完整的等级测评报告自动化审核解决方案：

1. **报告拆分工具** (`split_report.py`) - 将完整的等级测评报告按章节自动拆分
2. **自动审核工具** (`notebooklm_auto_review/`) - 基于 Google NotebookLM 进行智能化审核
3. **审核清单** (`checklist.md`) - 预置 11 个大类、16 个问题的专业审核 checklist

## 快速开始

### 1. 拆分测评报告

```bash
python split_report.py report.docx ./chapters
```

### 2. 安装审核工具环境

```bash
cd notebooklm_auto_review
python setup.py
```

### 3. 登录 Google 账号

```bash
python login_notebooklm.py
```

### 4. 运行自动审核

```bash
# 审核全部章节
python auto_review.py --input ./chapters --checklist ../checklist.md

# 只审核指定段落
python auto_review.py -i ./chapters -c ../checklist.md -s 1
```

### 5. 查看结果

审核结果输出到 `notebooklm_auto_review/results/` 目录：
- `review_results_*.json` - 详细 JSON 结果
- `summary_*.md` - Markdown 汇总报告
- `review_*.log` - 运行日志

## 配置说明

编辑 `notebooklm_auto_review/config.yaml`：

```yaml
# Google 账号
# google_account: your-email@gmail.com

# Notebook 配置
notebook_name: "等级测评报告审核"
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
├── 高风险判定指引.md             # 高风险判定参考
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

## 审核内容

| 段落 | 审核内容 | 问题数 |
|------|----------|--------|
| 1 | 附录 D（单项测评结果记录） | 4 |
| 2 | 整体测评 | 1 |
| 3 | 等级测评结论 | 1 |
| 4 | 重大风险隐患及整改建议 | 1 |
| 5 | 涉及到的时间问题 | 1 |
| 6 | 被测对象描述 | 1 |
| 7 | 单项测评结果分析 | 3 |
| 8 | 安全问题风险分析 | 1 |
| 9 | 安全整改建议 | 1 |
| 10 | 附录 A（被测对象资产） | 1 |
| 11 | 错别字 | 1 |

## 注意事项

- `.auth/` 目录包含 Cookie 认证信息，不会同步到 Git
- 实际的 `.docx` 报告文件不应提交到仓库
- Cookie 有效期约 30 天，过期需重新登录

## License

MIT
