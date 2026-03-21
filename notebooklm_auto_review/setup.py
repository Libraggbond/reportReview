#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速入门脚本

检查环境、安装依赖、引导用户完成首次配置
"""

import subprocess
import sys
from pathlib import Path


def check_python():
    """检查 Python 版本"""
    print("检查 Python 版本...")
    if sys.version_info < (3, 9):
        print(f"❌ Python 版本过低：{sys.version}")
        print("需要 Python 3.9+")
        return False
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True


def install_dependencies():
    """安装依赖"""
    print("\n安装依赖...")
    requirements = Path(__file__).parent / "requirements.txt"

    if not requirements.exists():
        print("❌ 找不到 requirements.txt")
        return False

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
            check=True
        )
        print("✓ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败：{e}")
        return False


def install_playwright_browsers():
    """安装 Playwright 浏览器"""
    print("\n安装 Playwright 浏览器...")

    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
        print("✓ Playwright 浏览器安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 浏览器安装失败：{e}")
        return False


def check_config():
    """检查配置文件"""
    print("\n检查配置文件...")

    config_file = Path(__file__).parent / "config.yaml"

    if not config_file.exists():
        print("⚠️ 配置文件不存在，将使用默认配置")
        return True

    print("✓ 配置文件存在")
    return True


def main():
    """主函数"""
    print("=" * 60)
    print("NotebookLM 自动审核工具 - 快速入门")
    print("=" * 60)

    # 1. 检查 Python
    if not check_python():
        sys.exit(1)

    # 2. 安装依赖
    if not install_dependencies():
        sys.exit(1)

    # 3. 安装浏览器
    if not install_playwright_browsers():
        sys.exit(1)

    # 4. 检查配置
    check_config()

    print("\n" + "=" * 60)
    print("环境准备完成!")
    print("=" * 60)

    print("\n下一步操作:")
    print("")
    print("1. 编辑 config.yaml 配置你的 Google 账号（可选）")
    print("")
    print("2. 登录 NotebookLM:")
    print("   python login_notebooklm.py")
    print("")
    print("3. 运行自动审核:")
    print("   python auto_review.py --input ./chapters --checklist ./checklist.md")
    print("")
    print("详细说明请查看 README.md")
    print("")


if __name__ == "__main__":
    main()
