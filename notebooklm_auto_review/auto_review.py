#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动审核主脚本（分段版本）

根据 checklist 中的段落配置，自动选择对应文档后提交审核问题
"""

import asyncio
import os
import yaml
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from notebooklm_client import NotebookLMClient
from checklist_parser import (
    Checklist, ChecklistSection, Question,
    load_checklist, extract_documents_from_question,
    get_section_documents
)


def load_config() -> dict:
    """加载配置文件"""
    config_file = Path(__file__).parent / "config.yaml"

    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_document_files(input_dir: str) -> Dict[str, str]:
    """
    获取待审核的文档文件映射（文件名 -> 完整路径）

    Args:
        input_dir: 输入目录

    Returns:
        文档名称到路径的映射
    """
    path = Path(input_dir)
    doc_map = {}

    if not path.exists():
        return doc_map

    # 支持的文件扩展名
    extensions = {".docx", ".pdf", ".txt", ".md"}

    for ext in extensions:
        for file in path.glob(f"*{ext}"):
            doc_map[file.name] = str(file)
        for file in path.glob(f"*{ext.upper()}"):
            doc_map[file.name] = str(file)

    return doc_map


def setup_logger(output_dir: str) -> Tuple[Path, Path]:
    """
    配置日志

    Returns:
        (日志文件路径，结果文件路径)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = Path(output_dir) / f"review_{timestamp}.log"
    result_file = Path(output_dir) / f"review_results_{timestamp}.json"

    logger.remove()
    logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
        encoding="utf-8",
        rotation="10 MB"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO"
    )

    return log_file, result_file


async def upload_documents(
    client: NotebookLMClient,
    doc_map: Dict[str, str],
    required_docs: List[str],
    config: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    批量上传指定的文档

    Args:
        client: NotebookLM 客户端
        doc_map: 文档名称到路径的映射
        required_docs: 需要上传的文档列表
        config: 配置

    Returns:
        (是否成功，已上传的文档列表)
    """
    uploaded = []
    failed = []

    # 收集所有需要上传的文件路径
    file_paths = []
    for doc_name in required_docs:
        if doc_name in doc_map:
            file_paths.append(doc_map[doc_name])
            uploaded.append(doc_name)
        else:
            logger.warning(f"文档不存在：{doc_name}")
            failed.append(doc_name)

    if not file_paths:
        return len(failed) == 0, uploaded

    # 批量上传所有文档
    try:
        result = await client.upload_documents_batch(file_paths)
        # 等待上传完成
        await asyncio.sleep(3)
        return len(failed) == 0, uploaded
    except Exception as e:
        logger.error(f"批量上传失败：{e}")
        return False, []


async def review_section(
    client: NotebookLMClient,
    section: ChecklistSection,
    doc_map: Dict[str, str],
    config: Dict[str, Any],
    uploaded_docs: List[str]
) -> Dict[str, Any]:
    """
    审核单个段落

    Args:
        client: NotebookLM 客户端
        section: 段落对象
        doc_map: 文档名称到路径的映射
        config: 配置
        uploaded_docs: 已上传的文档列表

    Returns:
        审核结果
    """
    logger.info("=" * 60)
    logger.info(f"审核段落：{section.id}、{section.title}")
    logger.info("=" * 60)

    # 获取该段落需要的文档（所有问题的并集）
    section_docs = get_section_documents(section)

    # 获取段落配置的文档（仅 #source: 配置的，不包含问题中提取的）
    section_configured_docs = [d for d in section.sources if d in doc_map or d in uploaded_docs]

    # 过滤出实际存在的文档
    available_docs = [d for d in section_docs if d in doc_map or d in uploaded_docs]

    logger.info(f"该段落涉及文档：{', '.join(available_docs)}")
    if section_configured_docs:
        logger.info(f"段落配置的文档（#source:）：{', '.join(section_configured_docs)}")

    results = {
        "section_id": section.id,
        "section_title": section.title,
        "sources": section_docs,
        "timestamp": datetime.now().isoformat(),
        "questions": [],
        "errors": []
    }

    # 逐个问题审核
    for question in section.questions:
        logger.info(f"\n问题 {section.id}-{question.id}: {question.content[:60].replace(chr(10), ' ')}...")

        # 从问题中提取应该参考的文档
        question_docs = extract_documents_from_question(question.content)

        # 使用相关的已上传文档
        relevant_docs = [d for d in question_docs if d in uploaded_docs]

        # 如果问题中没有明确提到文档，优先使用段落配置的文档（#source:）
        # 如果段落没有配置文档，则使用全部已上传文档（让 NotebookLM 自己判断）
        # 注意：不使用该段落其他问题中提到的文档作为 fallback，
        # 因为那会导致无关文档被错误地选中
        if not relevant_docs:
            if section_configured_docs:
                relevant_docs = section_configured_docs
            else:
                # 段落没有配置文档且问题中没有提到文档，使用全部已上传文档
                relevant_docs = uploaded_docs

        logger.info(f"参考文档：{relevant_docs}")

        try:
            # 构建提问内容
            full_question = question.content

            # 提问（带文档源选择）
            answer = await client.ask_question(full_question, relevant_docs if relevant_docs else None)

            if answer:
                results["questions"].append({
                    "section_id": section.id,
                    "section_title": section.title,
                    "question_id": question.id,
                    "question": question.content,
                    "reference_docs": relevant_docs,
                    "answer": answer,
                    "timestamp": datetime.now().isoformat()
                })
                logger.info(f"✓ 回答长度：{len(answer)} 字符")
            else:
                results["questions"].append({
                    "section_id": section.id,
                    "section_title": section.title,
                    "question_id": question.id,
                    "question": question.content,
                    "reference_docs": relevant_docs,
                    "answer": "⚠️ 未获取到回答",
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"问题处理失败：{e}")
            results["questions"].append({
                "section_id": section.id,
                "section_title": section.title,
                "question_id": question.id,
                "question": question.content,
                "reference_docs": relevant_docs,
                "answer": f"❌ 错误：{str(e)}",
                "timestamp": datetime.now().isoformat()
            })

        # 请求间隔
        await asyncio.sleep(config.get("request_interval", 3000) / 1000)

    logger.info(f"段落审核完成：{section.title}")
    return results


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="NotebookLM 自动审核工具（分段版本）")
    parser.add_argument(
        "--input", "-i",
        default="./chapters",
        help="输入目录（包含待审核文档）"
    )
    parser.add_argument(
        "--checklist", "-c",
        default="./checklist.md",
        help="审核清单文件路径"
    )
    parser.add_argument(
        "--output", "-o",
        default="./results",
        help="输出目录"
    )
    parser.add_argument(
        "--section", "-s",
        type=int,
        default=None,
        help="只审核指定段落（ID），不填则审核全部"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config()

    # 设置输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    config["output_dir"] = str(output_dir)

    # 配置日志
    log_file, result_file = setup_logger(str(output_dir))

    logger.info("=" * 60)
    logger.info("NotebookLM 自动审核工具（分段版本）")
    logger.info("=" * 60)

    # 加载审核清单
    checklist_path = Path(args.checklist)
    if not checklist_path.exists():
        logger.error(f"找不到审核清单：{checklist_path}")
        return

    logger.info(f"加载审核清单：{checklist_path}")
    checklist = load_checklist(str(checklist_path))

    # 统计问题总数
    total_questions = sum(len(s.questions) for s in checklist.sections)

    logger.info(f"共 {len(checklist.sections)} 个段落，{total_questions} 个问题")
    logger.info(f"涉及 {len(checklist.get_all_documents())} 个文档")

    # 显示所有涉及的文档
    logger.info("\n涉及文档列表:")
    for i, doc in enumerate(checklist.get_all_documents(), 1):
        logger.info(f"  {i}. {doc}")

    # 获取文档映射
    doc_map = get_document_files(args.input)
    logger.info(f"\n输入目录中找到 {len(doc_map)} 个文档")

    # 检查缺少的文档
    missing_docs = []
    for doc in checklist.get_all_documents():
        if doc not in doc_map:
            missing_docs.append(doc)

    if missing_docs:
        logger.warning(f"\n缺少 {len(missing_docs)} 个文档:")
        for doc in missing_docs:
            logger.warning(f"  - {doc}")

    # 创建客户端
    client = NotebookLMClient(config)

    # 启动浏览器
    logger.info("正在启动浏览器...")
    await client.launch_browser()

    all_results = []

    try:
        # 登录
        logger.info("正在登录 NotebookLM...")
        if not await client.login():
            logger.error("登录失败，请先运行 login_notebooklm.py 登录")
            return

        logger.info("登录成功!")

        # 优先使用配置中的 notebook_url
        notebook_url = config.get("notebook_url")
        notebook_name = config.get("notebook_name", "等级测评报告审核")

        if notebook_url:
            logger.info(f"使用 Notebook URL: {notebook_url}")
            await client.open_notebook_by_url(notebook_url)
        else:
            logger.info(f"使用 Notebook: {notebook_name}")
            # 尝试导航到已存在的 Notebook
            if not await client.navigate_to_notebook(notebook_name):
                # 如果不存在，创建新的
                logger.info("未找到现有 Notebook，创建新的...")
                notebook_id = await client.create_notebook(notebook_name)
                if notebook_id:
                    await client.open_notebook(notebook_id)

        # 打开 Notebook 后，先删除所有原有的文档源
        logger.info("\n" + "=" * 60)
        logger.info("清理原有文档源...")
        logger.info("=" * 60)
        await client.remove_all_sources()
        await asyncio.sleep(3)

        # 确定要审核的段落
        sections_to_review = checklist.sections
        if args.section is not None:
            sections_to_review = [s for s in checklist.sections if s.id == str(args.section)]
            if not sections_to_review:
                logger.error(f"未找到段落 ID: {args.section}")
                return
            logger.info(f"只审核段落：{args.section}")

        # 首先上传所有需要的文档
        logger.info("\n" + "=" * 60)
        logger.info("开始上传文档...")
        logger.info("=" * 60)

        all_needed_docs = checklist.get_all_documents()
        success, uploaded_docs = await upload_documents(
            client, doc_map, all_needed_docs, config
        )

        logger.info(f"\n上传完成：{len(uploaded_docs)}/{len(all_needed_docs)} 个文档")
        if uploaded_docs:
            logger.info("已上传:")
            for doc in uploaded_docs:
                logger.info(f"  ✓ {doc}")
        if success:
            logger.info("所有文档上传成功!")
        else:
            logger.warning("部分文档上传失败，继续执行...")

        # 等待文档处理完成
        await asyncio.sleep(5)

        # 逐段审核
        for section in sections_to_review:
            result = await review_section(
                client, section, doc_map, config, uploaded_docs
            )
            all_results.append(result)

            # 保存中间结果
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)

            logger.info(f"\n段落结果已保存：{result_file}")

        # 生成汇总报告
        generate_summary_report(all_results, str(output_dir))

        logger.info("=" * 60)
        logger.info("所有段落审核完成!")
        logger.info(f"结果保存在：{output_dir}")
        logger.info(f"日志文件：{log_file}")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("用户中断")
        logger.info("已执行的结果已保存")
    except Exception as e:
        logger.exception(f"审核过程出错：{e}")
    finally:
        await client.close()


def clean_answer_text(answer: str) -> str:
    """
    清理回答文本：去除引用数字、优化格式

    Args:
        answer: 原始回答文本

    Returns:
        清理后的文本
    """
    import re

    cleaned = answer

    # 1. 去除 more_horiz/more_vert 标记及其前面的数字
    cleaned = re.sub(r'\d*more_horiz', '', cleaned)
    cleaned = re.sub(r'\d*more_vert', '', cleaned)

    # 2. 删除中文句号前的引用数字 (如 "设备 4。" → "设备。")
    cleaned = re.sub(r'(?<=[^\d\s])\s*(\d+)。', '。', cleaned)

    # 3. 优化列表格式
    lines = cleaned.split('\n')
    formatted_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            formatted_lines.append(stripped)

    cleaned = '\n'.join(formatted_lines)

    # 4. 修复常见格式问题
    # 中文文字间不应有空格
    cleaned = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', cleaned)
    # 连续空行压缩
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # 5. 优化分段
    cleaned = cleaned.replace('-' * 80, '\n\n---\n\n')

    return cleaned


def generate_summary_report(results: List[Dict], output_dir: str) -> None:
    """生成汇总报告"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 统计段落和问题数量
    total_sections = len(results)
    total_questions = sum(len(r.get('questions', [])) for r in results)

    report_lines = [
        "# NotebookLM 自动审核汇总报告",
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
        report_lines.append(f"审核时间：{result['timestamp']}")
        report_lines.append(f"涉及文档：{', '.join(result['sources'])}")
        report_lines.append("")

        if result.get("errors"):
            report_lines.append("### 错误信息")
            for error in result["errors"]:
                report_lines.append(f"- {error}")
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

    report_path = Path(output_dir) / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    logger.info(f"汇总报告已保存：{report_path}")


if __name__ == "__main__":
    asyncio.run(main())
