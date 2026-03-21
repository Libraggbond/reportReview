#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审核清单解析器 v2 - 支持新的 checklist 格式

格式说明:
## 1、段落标题
#source: 文档 1.docx, 文档 2.docx (可选)

### 问题 1:
```
问题内容 1
问题内容 2
```

### 问题 2:
```
问题内容
```
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Question:
    """单个问题"""
    id: str                    # 问题 ID（如 "1"）
    content: str               # 问题完整内容
    raw_lines: List[str]       # 原始行


@dataclass
class ChecklistSection:
    """审核清单段落"""
    id: str                    # 段落 ID（如 "1"）
    title: str                 # 段落标题（如 "附录 D（单项测评结果记录）"）
    sources: List[str]         # 关联的文档列表
    questions: List[Question]  # 问题列表


@dataclass
class Checklist:
    """审核清单"""
    sections: List[ChecklistSection] = field(default_factory=list)
    all_documents: set = field(default_factory=set)

    def get_sections(self) -> List[ChecklistSection]:
        return self.sections

    def get_all_documents(self) -> List[str]:
        return sorted(list(self.all_documents))


def parse_checklist(checklist_path: str) -> Checklist:
    """
    解析审核清单文件

    Args:
        checklist_path: 清单文件路径

    Returns:
        Checklist 对象
    """
    with open(checklist_path, "r", encoding="utf-8") as f:
        content = f.read()

    checklist = Checklist()
    current_section: Optional[ChecklistSection] = None
    current_sources: List[str] = []
    current_question_id: str = ""
    in_code_block = False
    code_block_content = []
    question_lines = []

    lines = content.split("\n")

    for line in lines:
        # 检测代码块开始/结束
        if line.strip().startswith("```"):
            if in_code_block:
                # 代码块结束，保存问题
                if current_section and code_block_content:
                    question_content = "\n".join(code_block_content).strip()
                    if question_content:
                        q = Question(
                            id=current_question_id,
                            content=question_content,
                            raw_lines=code_block_content.copy()
                        )
                        current_section.questions.append(q)
                        # 从问题内容中提取文档
                        extracted_docs = extract_documents_from_question(question_content)
                        for doc in extracted_docs:
                            checklist.all_documents.add(doc)
                code_block_content = []
                in_code_block = False
            else:
                # 代码块开始
                in_code_block = True
            continue

        # 如果在代码块内，收集内容
        if in_code_block:
            code_block_content.append(line)
            continue

        # 跳空行
        if not line.strip():
            continue

        # 检测段落标题 (## 1、标题)
        section_match = re.match(r'^##\s*(\d+)[、.]\s*(.+)$', line.strip())
        if section_match:
            # 保存之前的段落
            if current_section:
                checklist.sections.append(current_section)

            section_id = section_match.group(1)
            section_title = section_match.group(2).strip()
            current_section = ChecklistSection(
                id=section_id,
                title=section_title,
                sources=current_sources.copy(),
                questions=[]
            )
            current_sources = []
            continue

        # 检测文档源 (#source: ...)
        source_match = re.match(r'^#source:\s*(.+)$', line.strip(), re.IGNORECASE)
        if source_match:
            sources_str = source_match.group(1)
            sources = [s.strip() for s in sources_str.split(",")]
            current_sources.extend(sources)
            for src in sources:
                checklist.all_documents.add(src)
            continue

        # 检测问题标题 (### 问题 X: 或 ### 问题 X：)
        question_match = re.match(r'^###\s*问题\s*(\d+)\s*[:：]?\s*$', line.strip())
        if question_match:
            current_question_id = question_match.group(1)
            continue

    # 添加最后一个段落
    if current_section:
        checklist.sections.append(current_section)

    return checklist


def extract_documents_from_question(question: str) -> List[str]:
    """
    从问题中提取文档名称

    Args:
        question: 问题文本

    Returns:
        文档名称列表
    """
    documents = []

    # 匹配带引号的文档名，支持英文单引号、双引号和中文引号
    # \u2018 = ' (中文左引号), \u2019 = ' (中文右引号)
    pattern = r"[\'\"\u2018\u2019]([^\u2018\u2019\'\"]+?\.(?:docx|pdf|txt|md|doc))[\u2018\u2019\'\"]"
    matches = re.findall(pattern, question, re.IGNORECASE)
    documents.extend(matches)

    return list(set(documents))


def get_section_documents(section: ChecklistSection) -> List[str]:
    """获取段落关联的文档列表"""
    docs = set(section.sources)
    for question in section.questions:
        extracted = extract_documents_from_question(question.content)
        docs.update(extracted)
    return sorted(list(docs))


def format_question_for_notebooklm(question: Question, section: ChecklistSection) -> str:
    """
    格式化问题为 NotebookLM 提问格式

    Args:
        question: 问题对象
        section: 所属段落

    Returns:
        格式化后的提问
    """
    # 提取该问题涉及的文档
    docs = extract_documents_from_question(question.content)

    if docs:
        doc_list = ", ".join(docs)
        return f"根据以下文档：{doc_list}。\n\n{question.content}"
    else:
        return question.content


def load_checklist(checklist_path: str) -> Checklist:
    """加载审核清单的便捷函数"""
    return parse_checklist(checklist_path)


def print_checklist_summary(checklist: Checklist) -> None:
    """打印清单摘要"""
    print("\n" + "=" * 60)
    print("审核清单解析结果")
    print("=" * 60)

    print(f"\n段落数量：{len(checklist.sections)}")
    print(f"涉及文档：{len(checklist.all_documents)}")

    print("\n涉及文档列表:")
    for i, doc in enumerate(checklist.get_all_documents(), 1):
        print(f"  {i}. {doc}")

    print("\n" + "=" * 60)
    print("段落详情")
    print("=" * 60)

    for section in checklist.sections:
        print(f"\n## {section.id}、{section.title}")
        print(f"   关联文档：{', '.join(section.sources) if section.sources else '（自动提取）'}")
        print(f"   问题数量：{len(section.questions)}")

        docs = get_section_documents(section)
        if docs:
            print(f"   实际涉及：{', '.join(docs)}")

        for q in section.questions:
            preview = q.content[:60].replace("\n", " ")
            print(f"   - 问题{q.id}: {preview}...")


def main():
    """测试入口"""
    import sys

    if len(sys.argv) < 2:
        checklist_path = "checklist.md"
    else:
        checklist_path = sys.argv[1]

    if not Path(checklist_path).exists():
        print(f"文件不存在：{checklist_path}")
        sys.exit(1)

    checklist = parse_checklist(checklist_path)
    print_checklist_summary(checklist)


if __name__ == "__main__":
    main()
