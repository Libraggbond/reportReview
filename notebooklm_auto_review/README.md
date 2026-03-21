# NotebookLM 自动审核工具

通过浏览器自动化将文档上传到 Google NotebookLM 并进行自动审核。

## 功能特性

- 自动上传 DOCX/PDF 文档到 NotebookLM
- **支持按 checklist 段落分段提交审核**
- **自动根据段落内容选择关联文档**
- 自动执行预设的审核问题
- 收集并整理审核结果
- 支持批量文档处理

## 环境要求

- Python 3.9+
- Google 账号（已访问 NotebookLM 权限）
- Chrome 浏览器

## 安装

```bash
# 一键安装环境和依赖
python setup.py
```

或手动安装：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## 配置

编辑 `config.yaml` 文件：

```yaml
# Google 账号（也可使用环境变量 GOOGLE_ACCOUNT）
# google_account: your-email@gmail.com

# 输出目录
output_dir: ./results

# Notebook 配置
notebook_name: "等级测评报告审核"

# 超时设置（秒）
upload_timeout: 300
processing_timeout: 600

# 请求间隔（毫秒）- 避免触发反自动化
request_interval: 3000

# 代理配置（可选）
# 无认证代理
proxy: "http://proxy.example.com:8080"

# 或带认证的代理
proxy:
  server: "http://proxy.example.com:8080"
  username: "your_username"
  password: "your_password"
```

### 代理配置说明

支持两种代理格式：

1. **简单格式**（无认证）：
   ```yaml
   proxy: "http://proxy.example.com:8080"
   ```

2. **完整格式**（带认证）：
   ```yaml
   proxy:
     server: "http://proxy.example.com:8080"
     username: "user"
     password: "pass"
     bypass: "localhost,127.0.0.1"  # 可选，绕过代理的地址
   ```

**测试代理配置：**
```bash
python test_proxy.py
```

## Checklist 格式

Checklist 文件使用以下格式：

```markdown
## 1、段落标题

### 问题 1:
```
1 从'文档 A.docx'中的内容...
2 列出'文档 B.docx'中的内容...
```

### 问题 2:
```
1 对比文档 A 和文档 B 的内容...
```

## 2、整体测评
#source: 4_整体测评.docx, 附录_单项测评结果记录.docx

### 问题 1:
```
1 从'4_整体测评.docx'的'整体测评结果汇总'中列出...
```
```

**格式说明：**
- `## 1、段落标题` - 大段落标题（必须）
- `### 问题 X:` - 问题分组（必须）
- 问题内容放在代码块 ` ``` ` 中（必须）
- `#source:` 指定该段落需要参考的文档（可选，如不指定则自动从问题中提取）

## 使用方法

### 1. 登录 Google 账号

首次运行需要手动登录：

```bash
python login_notebooklm.py
```

这会打开浏览器，登录 Google 账号并保存 Cookie。

### 2. 运行自动审核

```bash
# 审核所有章节
python auto_review.py --input ./chapters --checklist checklist.md

# 只审核指定段落（如第 1 段）
python auto_review.py --input ./chapters --checklist checklist.md --section 1

# 指定输出目录
python auto_review.py -i ./chapters -c checklist.md -o ./my_results
```

### 3. 查看结果

审核结果保存在 `results/` 目录下：
- `review_results_*.json` - 详细 JSON 结果
- `summary_*.md` - Markdown 汇总报告
- `review_*.log` - 运行日志

## 目录结构

```
notebooklm_auto_review/
├── config.yaml              # 配置文件
├── requirements.txt         # 依赖
├── setup.py                 # 一键安装脚本
├── login_notebooklm.py      # 登录脚本
├── auto_review.py           # 主审核脚本
├── notebooklm_client.py     # NotebookLM 操作封装
├── checklist_parser.py      # Checklist 解析器
├── README.md                # 本文档
├── .github/workflows/
│   └── auto-review.yml      # GitHub Actions 配置
├── .auth/                   # Cookie 存储目录（自动生成）
└── results/                 # 审核结果输出（自动生成）
```

## 命令行参数

### auto_review.py

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| --input | -i | 输入目录（包含待审核文档） | ./chapters |
| --checklist | -c | 审核清单文件路径 | ./checklist.md |
| --output | -o | 输出目录 | ./results |
| --section | -s | 只审核指定段落 ID | 全部 |

### 使用示例

```bash
# 审核全部段落
python auto_review.py

# 审核第 3 段（等级测评结论）
python auto_review.py -s 3

# 从指定目录读取文档
python auto_review.py -i /path/to/docs -c checklist.md
```

## 审核流程

1. **加载 Checklist** - 解析段落和问题
2. **提取文档映射** - 识别每个段落/问题需要的文档
3. **登录 NotebookLM** - 使用保存的 Cookie 或手动登录
4. **创建/打开 Notebook** - 使用配置的 Notebook 名称
5. **上传文档** - 上传所有需要的文档
6. **逐段审核**：
   - 逐问题提交（自动在问题前添加文档上下文）
   - 等待并保存回答
7. **生成报告** - 输出 JSON 和 Markdown 格式结果

## 注意事项

1. **Cookie 有效期**：登录 Cookie 通常有效期为 30 天
2. **上传限制**：NotebookLM 每个 Notebook 最多支持 50 个文档
3. **速率限制**：默认每 3 秒发送一次请求，避免触发反自动化
4. **界面变化**：Google 可能更改网页结构，如脚本失效需更新选择器
5. **文档命名**：Checklist 中引用的文档名必须与实际文件名完全一致

## 故障排除

### Cookie 失效
```bash
# 删除 Cookie 重新登录
rm -rf .auth/cookies.json
python login_notebooklm.py
```

### 上传失败
检查网络连接，确保能访问 notebooklm.google.com

### 选择器失效
更新 `notebooklm_client.py` 中的 CSS 选择器

### 文档未找到
确保 Checklist 中引用的文档名与输入目录中的文件名完全匹配

### 解析 Checklist 失败
运行以下命令验证 Checklist 格式：
```bash
python checklist_parser.py checklist.md
```

## GitHub Actions 自动化

项目中包含 GitHub Actions 配置，可以在 CI/CD 中运行审核：

```yaml
# .github/workflows/auto-review.yml
```

配置 Secrets：
- `GOOGLE_ACCOUNT` - Google 账号（可选）

## 输出示例

### JSON 结果

```json
[
  {
    "section_id": "1",
    "section_title": "附录 D（单项测评结果记录）",
    "sources": ["附录_单项测评结果记录.docx", "2_被测对象描述.docx"],
    "questions": [
      {
        "section_id": "1",
        "question_id": "1",
        "question": "从'附录_单项测评结果记录.docx'中的'安全物理环境'...",
        "reference_docs": ["附录_单项测评结果记录.docx"],
        "answer": "根据文档内容...",
        "timestamp": "2026-03-20T10:30:00"
      }
    ]
  }
]
```

### Markdown 汇总

```markdown
# NotebookLM 自动审核汇总报告

生成时间：2026-03-20 10:30:00
审核段落数：11
审核问题数：26

================================================================================

## 1、附录 D（单项测评结果记录）
审核时间：2026-03-20T10:30:00
涉及文档：0_报告首页及目录.docx, 2_被测对象描述.docx, 附录_单项测评结果记录.docx

### 审核结果

**问题 1:**
从'附录_单项测评结果记录.docx'中的'安全物理环境'、'安全计算环境'中识别出相应的安全物理环境...

*参考文档:* 附录_单项测评结果记录.docx, 2_被测对象描述.docx

**回答:** 根据提供的文档内容，我从安全物理环境和安全计算环境中识别出以下资产...

---
```

## 相关文档

- [Checklist 解析器](checklist_parser.py) - 解析审核清单格式，支持测试命令
- [NotebookLM 客户端](notebooklm_client.py) - 浏览器自动化操作
- [配置文件](config.yaml) - 自定义配置选项
