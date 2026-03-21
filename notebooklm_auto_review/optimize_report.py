#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从现有 JSON 结果文件生成优化格式的汇总报告
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict


def clean_answer_text(answer: str) -> str:
    """
    清理回答文本：去除引用数字、优化格式

    Args:
        answer: 原始回答文本

    Returns:
        清理后的文本
    """
    cleaned = answer

    # 1. 去除 more_horiz/more_vert 标记及其前面的数字
    cleaned = re.sub(r'\d*more_horiz', '', cleaned)
    cleaned = re.sub(r'\d*more_vert', '', cleaned)

    # 2. 删除中文句号前的引用数字 (如 "设备 4。" → "设备。")
    cleaned = re.sub(r'(?<=[^\d\s])\s*(\d+)。', '。', cleaned)

    # 3. 优化列表格式 - 为 1. 2. 3. 这种编号添加换行分段
    # 匹配：数字 + 英文句点 + 中文（不在行首的情况）
    # 在编号前添加换行，使其单独成段
    cleaned = re.sub(r'([^\n])\s*(\d+\.\s+[\u4e00-\u9fff])', r'\1\n\n\2', cleaned)

    # 4. 优化列表格式 - 去除每行前后空格
    lines = cleaned.split('\n')
    formatted_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            formatted_lines.append(stripped)

    cleaned = '\n'.join(formatted_lines)

    # 5. 修复常见格式问题
    # 中文文字间不应有空格
    cleaned = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', cleaned)
    # 连续空行压缩
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # 6. 优化分段
    cleaned = cleaned.replace('-' * 80, '\n\n---\n\n')

    return cleaned


def generate_summary_report(results: List[Dict], output_path: str) -> None:
    """生成优化格式的汇总报告"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 统计段落和问题数量
    total_sections = len(results)
    total_questions = sum(len(r.get('questions', [])) for r in results)

    report_lines = [
        "# NotebookLM 自动审核汇总报告（优化格式）",
        "",
        f"生成时间：{timestamp}",
        "",
        f"审核段落数：{total_sections}",
        f"审核问题数：{total_questions}",
        "",
        "=" * 80,
        "",
    ]

    for result in results:
        report_lines.append(f"## {result['section_id']}、{result['section_title']}")
        report_lines.append(f"涉及文档：{', '.join(result['sources'])}")
        report_lines.append("")
        report_lines.append("### 审核结果")
        report_lines.append("")

        for q in result.get("questions", []):
            q_id = q.get('question_id', '')
            report_lines.append(f"#### 问题 {q_id}")
            report_lines.append("")
            report_lines.append(f"{q['question']}")
            report_lines.append("")
            report_lines.append(f"**参考文档:** {', '.join(q['reference_docs']) if q['reference_docs'] else '全部文档'}")
            report_lines.append("")
            report_lines.append("**回答:**")
            report_lines.append("")

            answer = q.get('answer', '')
            # 清理回答文本
            cleaned_answer = clean_answer_text(answer)

            if len(cleaned_answer) > 2000:
                # 长回答分段显示
                report_lines.append(f"{cleaned_answer[:2000]}")
                report_lines.append("")
                report_lines.append("*（完整回答见 JSON 结果文件）*")
            else:
                report_lines.append(f"{cleaned_answer}")

            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"优化报告已生成：{output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="从 JSON 结果生成优化格式的汇总报告")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入的 JSON 结果文件路径"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出的 markdown 报告路径（默认在同目录下生成 summary_optimized_*.md）"
    )

    args = parser.parse_args()

    # 读取 JSON 结果
    with open(args.input, "r", encoding="utf-8") as f:
        results = json.load(f)

    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        input_dir = Path(args.input).parent
        output_path = str(input_dir / f"summary_optimized_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")

    generate_summary_report(results, output_path)


if __name__ == "__main__":
    main()
