#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NotebookLM 登录脚本

首次运行需要手动登录 Google 账号并保存 Cookie
"""

import asyncio
import yaml
from pathlib import Path
from loguru import logger
from notebooklm_client import NotebookLMClient


def load_config() -> dict:
    """加载配置文件"""
    config_file = Path(__file__).parent / "config.yaml"

    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("NotebookLM 登录工具")
    logger.info("=" * 60)

    config = load_config()

    # 创建客户端
    client = NotebookLMClient(config)

    # 启动浏览器
    logger.info("正在启动浏览器...")
    await client.launch_browser()

    try:
        # 执行登录
        success = await client.login()

        if success:
            logger.info("=" * 60)
            logger.info("登录成功！Cookie 已保存")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Cookie 保存在：.auth/cookies.json")
            logger.info("下次运行 auto_review.py 时会自动使用保存的 Cookie 登录")
            logger.info("")
            logger.info("注意：")
            logger.info("  - Cookie 通常有效期为 30 天")
            logger.info("  - 如果登录失效，请重新运行此脚本")
            logger.info("  - 如需切换账号，请删除 .auth/cookies.json 后重新登录")
        else:
            logger.error("登录失败，请检查网络连接或重试")

    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.exception(f"登录过程出错：{e}")
    finally:
        # 关闭浏览器
        logger.info("正在关闭浏览器...")
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
