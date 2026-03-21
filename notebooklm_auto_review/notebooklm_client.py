#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NotebookLM 客户端 - 封装浏览器自动化操作
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger


class NotebookLMClient:
    """NotebookLM 浏览器自动化客户端"""

    NOTEBOOKLM_URL = "https://notebooklm.google.com"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.auth_dir = Path(__file__).parent / ".auth"
        self.auth_dir.mkdir(exist_ok=True)
        self.cookie_file = self.auth_dir / "cookies.json"

        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 解析代理配置
        self.proxy = self._parse_proxy(config.get("proxy"))

    def _parse_proxy(self, proxy_config: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """
        解析代理配置

        支持两种格式：
        1. 字典格式：{"server": "...", "username": "...", "password": "..."}
        2. 字符串格式："http://proxy.example.com:8080"

        Args:
            proxy_config: 代理配置

        Returns:
            标准化的代理配置字典或 None
        """
        if not proxy_config:
            return None

        if isinstance(proxy_config, str):
            # 字符串格式，直接作为 server
            return {"server": proxy_config}

        if isinstance(proxy_config, dict):
            # 字典格式，验证必要字段
            if "server" in proxy_config:
                return proxy_config

        return None

    async def launch_browser(self) -> None:
        """启动浏览器"""
        playwright = await async_playwright().start()

        # 构建浏览器启动参数
        launch_args = {
            "headless": self.config.get("headless", False),
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        }

        # 添加慢动作配置
        slow_mo = self.config.get("slow_mo", 1000)
        if slow_mo:
            launch_args["slow_mo"] = slow_mo

        self.browser = await playwright.chromium.launch(**launch_args)

        # 构建上下文参数
        context_args = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 添加代理配置
        if self.proxy:
            context_args["proxy"] = self.proxy
            logger.info(f"使用代理：{self.proxy.get('server')}")

        # 创建上下文
        self.context = await self.browser.new_context(**context_args)

        # 设置额外的反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

        self.page = await self.context.new_page()

    async def close(self) -> None:
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()

    async def load_cookies(self) -> bool:
        """加载保存的 Cookie"""
        if not self.cookie_file.exists():
            return False

        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await self.context.add_cookies(cookies)
            logger.info("已加载保存的 Cookie")
            return True
        except Exception as e:
            logger.error(f"加载 Cookie 失败：{e}")
            return False

    async def save_cookies(self) -> None:
        """保存 Cookie"""
        try:
            cookies = await self.context.cookies()
            # 过滤 NotebookLM 相关的 Cookie
            notebooklm_cookies = [c for c in cookies if "notebooklm" in c.get("domain", "") or "google" in c.get("domain", "")]
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(notebooklm_cookies, f, indent=2)
            logger.info("Cookie 已保存")
        except Exception as e:
            logger.error(f"保存 Cookie 失败：{e}")

    async def login(self) -> bool:
        """
        登录 NotebookLM

        Returns:
            bool: 是否登录成功
        """
        logger.info("正在访问 NotebookLM...")

        await self.page.goto(self.NOTEBOOKLM_URL, timeout=self.config.get("page_timeout", 60000))
        await asyncio.sleep(5)

        # 检查是否已登录
        if await self.is_logged_in():
            logger.info("已登录状态")
            await self.save_cookies()
            return True

        # 尝试加载 Cookie
        if await self.load_cookies():
            await self.page.reload()
            await asyncio.sleep(5)

            if await self.is_logged_in():
                logger.info("通过 Cookie 自动登录成功")
                await self.save_cookies()
                return True

        logger.warning("需要手动登录")
        logger.info("请在浏览器窗口中登录 Google 账号...")
        logger.info("提示：登录成功后，浏览器会自动跳转到 notebooklm.google.com")

        # 主动轮询检测登录状态（最长 10 分钟）
        max_wait = 600  # 10 分钟
        check_interval = 5  # 每 5 秒检查一次
        elapsed = 0

        while elapsed < max_wait:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # 检查是否已登录
            if await self.is_logged_in():
                await asyncio.sleep(3)  # 等待页面完全加载
                logger.info("登录成功！")
                await self.save_cookies()
                logger.info(f"Cookie 已保存到：{self.cookie_file}")
                return True

            if elapsed % 30 == 0:
                logger.info(f"等待登录中... ({elapsed}/{max_wait} 秒)")

        logger.error("登录超时")
        return False

    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            # 检查当前 URL 是否是 NotebookLM
            current_url = self.page.url
            if "notebooklm.google.com" in current_url and 'signin' not in current_url:
                logger.debug(f"当前 URL: {current_url}")
                # URL 已经是 NotebookLM，尝试检查页面元素确认
                try:
                    has_notebook_link = await self.page.query_selector('a[href*="/notebooks"]')
                    has_add_source = await self.page.query_selector('button:has-text("添加源"), button:has-text("Add source")')
                    if has_notebook_link or has_add_source:
                        logger.debug("检测到 NotebookLM 页面元素，已登录")
                        return True
                    # 即使没检测到元素，URL 正确也认为已登录
                    logger.debug("URL 正确，认为已登录")
                    return True
                except:
                    # 页面可能还在加载，但 URL 正确就认为已登录
                    logger.debug("URL 正确，认为已登录")
                    return True
            return False
        except Exception as e:
            logger.debug(f"检查登录状态失败：{e}")
            return False

    async def create_notebook(self, name: str) -> Optional[str]:
        """
        创建新的 Notebook

        Args:
            name: Notebook 名称

        Returns:
            Notebook ID 或 None
        """
        logger.info(f"创建 Notebook: {name}")

        # 点击新建 Notebook 按钮
        try:
            # 查找"新建 Notebook"按钮
            create_btn = await self.page.wait_for_selector(
                'button:has-text("新建 Notebook"), button:has-text("Create notebook"), [role="button"]:has-text("新建")',
                timeout=10000
            )
            await create_btn.click()
            await asyncio.sleep(2)

            # 输入 Notebook 名称
            name_input = await self.page.wait_for_selector(
                'input[placeholder*="名称"], input[placeholder*="name"]',
                timeout=5000
            )
            await name_input.fill(name)
            await asyncio.sleep(1)

            # 点击确认
            confirm_btn = await self.page.wait_for_selector(
                'button:has-text("确定"), button:has-text("Create"), button:has-text("创建")',
                timeout=5000
            )
            await confirm_btn.click()
            await asyncio.sleep(3)

            # 获取 Notebook ID（从 URL）
            current_url = self.page.url
            notebook_id = current_url.split("/notebooks/")[-1] if "/notebooks/" in current_url else None

            if notebook_id:
                logger.info(f"Notebook 创建成功，ID: {notebook_id}")
                return notebook_id

        except Exception as e:
            logger.error(f"创建 Notebook 失败：{e}")

        return None

    async def upload_documents_batch(self, file_paths: List[str]) -> List[str]:
        """
        批量上传文档 - 一次性选择多个文件上传

        Args:
            file_paths: 文件路径列表

        Returns:
            成功上传的文件名列表
        """
        if not file_paths:
            return []

        logger.info(f"批量上传 {len(file_paths)} 个文档...")

        try:
            # 使用 JavaScript 点击添加源按钮
            await self.page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button, [role="button"]');
                    for (let btn of buttons) {
                        const text = btn.textContent;
                        if (text.includes('添加源') || text.includes('Add source') || text === '+') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)

            # 等待对话框出现
            await self.page.wait_for_selector('.cdk-overlay-pane.mat-mdc-dialog-panel', timeout=10000)
            await asyncio.sleep(1)

            # 找到上传按钮并点击
            upload_btn = await self.page.wait_for_selector(
                'button:has-text("upload"), button:has-text("Upload"), button:has-text("上传")',
                timeout=10000
            )
            await upload_btn.click()
            await asyncio.sleep(2)

            # 找到文件输入框
            file_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000, state="attached")

            # 设置 multiple 属性以支持多文件选择
            await file_input.set_input_files(file_paths)

            logger.info("文件已设置")

            # 等待上传完成
            upload_timeout = self.config.get("upload_timeout", 300)
            logger.info(f"等待上传完成（最多 {upload_timeout} 秒）...")

            # 等待所有文档上传完成，返回实际上传成功的文档列表
            uploaded_count = await self.wait_for_batch_upload_complete(len(file_paths), upload_timeout)

            logger.info(f"批量上传完成：{uploaded_count}/{len(file_paths)} 个文档")

            # 获取实际上传成功的文档列表
            sources = await self.get_sources()
            uploaded_names = [s['name'] for s in sources]
            return uploaded_names

        except Exception as e:
            logger.error(f"批量上传失败：{e}")
            return []

    async def wait_for_batch_upload_complete(self, expected_count: int, timeout: int = 300) -> int:
        """等待批量上传完成

        Returns:
            实际上传成功的文档数量
        """
        start_time = time.time()
        last_count = 0

        while time.time() - start_time < timeout:
            try:
                # 检查是否有上传进度指示器
                progress = await self.page.query_selector('[role="progressbar"]')
                if progress:
                    await asyncio.sleep(2)
                    continue

                # 检查文档数量
                sources = await self.get_sources()
                current_count = len(sources)

                if current_count >= expected_count:
                    await asyncio.sleep(3)
                    return current_count

                # 如果数量稳定不变，认为上传完成
                if current_count > 0 and current_count == last_count:
                    await asyncio.sleep(3)
                    # 再次检查是否稳定
                    sources2 = await self.get_sources()
                    if len(sources2) == current_count:
                        logger.info(f"上传稳定：{current_count} 个文档")
                        return current_count

                last_count = current_count

            except Exception as e:
                logger.debug(f"检查上传状态失败：{e}")

            await asyncio.sleep(2)

        logger.warning(f"上传超时，返回当前数量：{last_count}")
        return last_count

    async def upload_document(self, file_path: str) -> bool:
        """上传文档 - 不弹出系统文件选择窗口"""
        logger.info(f"上传文档：{file_path}")

        try:
            # 使用 JavaScript 点击添加源按钮
            await self.page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button, [role="button"]');
                    for (let btn of buttons) {
                        const text = btn.textContent;
                        if (text.includes('添加源') || text.includes('Add source') || text === '+') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)

            # 等待对话框出现
            await self.page.wait_for_selector('.cdk-overlay-pane.mat-mdc-dialog-panel', timeout=10000)
            await asyncio.sleep(1)

            # 找到上传按钮并点击
            upload_btn = await self.page.wait_for_selector(
                'button:has-text("upload"), button:has-text("Upload"), button:has-text("上传")',
                timeout=10000
            )
            await upload_btn.click()
            await asyncio.sleep(2)

            # 找到文件输入框
            file_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000, state="attached")

            # 使用 set_input_files 直接设置文件（不会触发系统对话框）
            await file_input.set_input_files(file_path)

            logger.info("文件已设置")

            # 等待上传完成
            upload_timeout = self.config.get("upload_timeout", 300)
            logger.info(f"等待上传完成（最多 {upload_timeout} 秒）...")

            # 等待上传进度完成
            await self.wait_for_upload_complete(upload_timeout)

            logger.info(f"文档上传成功：{Path(file_path).name}")
            return True

        except Exception as e:
            logger.error(f"上传文档失败：{e}")
            return False

    async def wait_for_upload_complete(self, timeout: int = 300) -> bool:
        """等待上传完成"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 检查是否有上传进度指示器
                progress = await self.page.query_selector('[role="progressbar"]')
                if progress:
                    await asyncio.sleep(2)
                    continue

                # 检查文档是否已出现在源列表中
                await asyncio.sleep(3)
                return True

            except Exception:
                pass

            await asyncio.sleep(1)

        return False

    async def ask_question(self, question: str, source_docs: Optional[List[str]] = None) -> Optional[str]:
        """
        提问并获取回答

        Args:
            question: 问题文本
            source_docs: 可选的源文档名称列表，用于限定参考范围

        Returns:
            AI 回答或 None
        """
        logger.info(f"提问：{question[:50]}...")

        try:
            # 如果有指定源文档，先选择文档
            if source_docs:
                await self.select_sources(source_docs)
                await asyncio.sleep(1)

            # 使用 JavaScript 找到正确的输入框并设置值
            result = await self.page.evaluate(f"""
                () => {{
                    const textareas = document.querySelectorAll('textarea');
                    for (const ta of textareas) {{
                        if (ta.placeholder && ta.placeholder.includes('Start typing') &&
                            !ta.disabled && !ta.readOnly) {{
                            ta.value = `{question}`;
                            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)

            if not result:
                logger.error("未找到可用的输入框")
                return None

            await asyncio.sleep(1)

            # 使用 XPath 找到提交按钮并点击
            submit_btn = await self.page.query_selector(
                'xpath=/html/body/labs-tailwind-root/div/notebook/div/section[2]/chat-panel/omnibar/div/div/div/query-box/div/div/form/div/button/mat-icon/..'
            )
            if submit_btn:
                await submit_btn.click()
            else:
                # 备用方案：直接点击 button 内的 mat-icon 的父元素
                submit_btn = await self.page.query_selector('query-box form div button mat-icon')
                if submit_btn:
                    await submit_btn.click()

            await asyncio.sleep(2)

            # 等待回答
            processing_timeout = self.config.get("processing_timeout", 600)
            answer = await self.wait_for_answer(processing_timeout)

            if answer:
                logger.info(f"回答长度：{len(answer)} 字符")
                return answer
            return None

        except Exception as e:
            logger.error(f"提问失败：{e}")
            return None

    async def select_sources(self, source_names: List[str]) -> bool:
        """
        选择指定的文档源（用于限定 AI 回答范围）

        Args:
            source_names: 要选择的文档名称列表

        Returns:
            bool: 是否成功
        """
        logger.info(f"选择文档源：{source_names}")

        try:
            # 在 sources 面板中找到对应的文档并点击
            result = await self.page.evaluate(f"""
                (sourceNames) => {{
                    let selected = 0;
                    const allText = document.body.textContent;

                    for (const sourceName of sourceNames) {{
                        // 查找包含文档名称的元素
                        const elements = document.querySelectorAll('[class*="source"], [role="listitem"]');
                        for (const el of elements) {{
                            const text = el.textContent;
                            if (text && text.includes(sourceName)) {{
                                // 找到元素，点击它
                                el.click();
                                selected++;
                                break;
                            }}
                        }}
                    }}

                    return selected > 0;
                }}
            """, source_names)

            await asyncio.sleep(1)
            return result

        except Exception as e:
            logger.error(f"选择文档源失败：{e}")
            return False

    async def wait_for_answer(self, timeout: int = 600) -> Optional[str]:
        """等待 AI 回答"""
        start_time = time.time()
        last_answer = None

        while time.time() - start_time < timeout:
            try:
                # 检查是否有加载中状态
                loading = await self.page.query_selector(
                    '[role="status"], .loading, [aria-busy="true"], .spinner, mat-progress-spinner'
                )

                if loading:
                    logger.debug("回答生成中...")
                    await asyncio.sleep(2)
                    continue

                # 使用 JavaScript 从页面提取回答
                answer = await self.page.evaluate("""
                    () => {
                        const chatPanel = document.querySelector('.chat-panel-content');
                        if (!chatPanel) {
                            return null;
                        }

                        // 获取所有消息元素
                        const messages = Array.from(chatPanel.querySelectorAll('article, div[class*="message"], div[class*="response"]'));

                        if (messages.length === 0) {
                            return null;
                        }

                        // 获取最后一个消息（最新的回答）
                        const lastMessage = messages[messages.length - 1];
                        const fullText = lastMessage.textContent?.trim();

                        if (!fullText || fullText.length < 100) {
                            return null;
                        }

                        // 尝试从问题之后提取答案
                        // 找到问题的开始位置（以数字开头的问题）
                        const questionPatterns = [
                            /^\\d+\\s+/m,  // 以数字开头
                            /\\d+['\"\u2018\u2019]/,  // 数字后跟引号
                        ];

                        let questionIndex = -1;
                        for (const pattern of questionPatterns) {
                            const match = fullText.match(pattern);
                            if (match) {
                                questionIndex = match.index;
                                break;
                            }
                        }

                        if (questionIndex > 0) {
                            // 从问题之后提取
                            const afterQuestion = fullText.substring(questionIndex);
                            // 找到答案开始（通常是换行后）
                            const lines = afterQuestion.split('\\n');
                            let answerStart = false;
                            const answerLines = [];

                            for (const line of lines) {
                                if (answerStart) {
                                    if (line.trim().length > 10) {
                                        answerLines.push(line);
                                    }
                                } else if (line.includes('：') || line.includes(':')) {
                                    answerStart = true;
                                }
                            }

                            if (answerLines.length > 0) {
                                return answerLines.join('\\n').trim();
                            }
                        }

                        return fullText;
                    }
                """)

                if answer and len(answer) > 100:
                    # 检查是否还在变化
                    await asyncio.sleep(2)
                    new_answer = await self.page.evaluate("""
                        () => {
                            const chatPanel = document.querySelector('.chat-panel-content');
                            if (!chatPanel) return null;
                            const messages = Array.from(chatPanel.querySelectorAll('article, div[class*="message"], div[class*="response"]'));
                            if (messages.length === 0) return null;
                            return messages[messages.length - 1].textContent?.trim();
                        }
                    """)

                    if new_answer == answer or not new_answer:
                        logger.info(f"获取到回答：{len(answer)} 字符")
                        return answer
                    else:
                        last_answer = answer
                elif answer:
                    last_answer = answer

            except Exception as e:
                logger.debug(f"等待回答中：{e}")

            await asyncio.sleep(2)

        if last_answer:
            logger.info(f"超时但获取到回答：{len(last_answer)} 字符")
            return last_answer

        logger.warning("等待回答超时")
        return None

    async def get_notebooks(self) -> List[Dict[str, str]]:
        """获取 Notebook 列表"""
        logger.info("获取 Notebook 列表...")

        try:
            await self.page.goto(f"{self.NOTEBOOKLM_URL}/notebooks", timeout=30000)
            await asyncio.sleep(5)

            notebooks = []
            # 尝试多种选择器
            selectors = [
                'a[href*="/notebooks/"]',  # Notebook 链接
                '[role="listitem"] a',  # 列表项中的链接
                '.notebook-card a',  # Notebook 卡片
                'c-wiz a[href*="/notebooks/"]',  # c-wiz 组件中的链接
            ]

            seen_urls = set()

            for selector in selectors:
                elements = await self.page.query_selector_all(selector)
                for elem in elements:
                    try:
                        href = await elem.get_attribute("href")
                        if href and '/notebooks/' in href and href not in seen_urls:
                            seen_urls.add(href)
                            # 获取 Notebook 名称
                            text = await elem.inner_text()
                            if not text:
                                text = await elem.get_attribute("aria-label") or "未命名 Notebook"
                            notebooks.append({
                                "name": text.strip(),
                                "url": href,
                                "id": href.split("/notebooks/")[-1].split("?")[0].split("/")[0]
                            })
                    except:
                        continue

            logger.info(f"找到 {len(notebooks)} 个 Notebook")
            for nb in notebooks:
                logger.info(f"  - {nb['name']}: {nb['id']}")
            return notebooks

        except Exception as e:
            logger.error(f"获取 Notebook 列表失败：{e}")
            return []

    async def open_notebook(self, notebook_id: str) -> bool:
        """
        打开指定 Notebook

        Args:
            notebook_id: Notebook ID

        Returns:
            bool: 是否成功
        """
        logger.info(f"打开 Notebook: {notebook_id}")

        try:
            url = f"{self.NOTEBOOKLM_URL}/notebook/{notebook_id}"
            await self.page.goto(url, timeout=self.config.get("page_timeout", 60000))
            await asyncio.sleep(3)
            return True
        except Exception as e:
            logger.error(f"打开 Notebook 失败：{e}")
            return False

    async def open_notebook_by_url(self, url: str) -> bool:
        """
        通过 URL 直接打开 Notebook

        Args:
            url: Notebook 完整 URL

        Returns:
            bool: 是否成功
        """
        logger.info(f"打开 Notebook: {url}")

        try:
            await self.page.goto(url, timeout=self.config.get("page_timeout", 60000))
            await asyncio.sleep(3)
            return True
        except Exception as e:
            logger.error(f"打开 Notebook 失败：{e}")
            return False

    async def get_sources(self) -> List[Dict[str, str]]:
        """
        获取当前 Notebook 中的文档源列表

        Returns:
            文档源列表，每项包含 {name, id, selected}
        """
        logger.info("获取文档源列表...")

        try:
            # 等待源列表加载
            await asyncio.sleep(2)

            # 使用 JavaScript 直接获取文档源列表
            sources = await self.page.evaluate("""
                () => {
                    const sources = [];
                    const seen = new Set();

                    // 使用 single-source-container 选择器
                    document.querySelectorAll('.single-source-container').forEach(container => {
                        // 只获取 checkbox 之后的文本，排除按钮和图标
                        let text = '';
                        const checkbox = container.querySelector('input[type="checkbox"]');
                        if (checkbox) {
                            // 获取 checkbox 之后的文本节点
                            let foundCheckbox = false;
                            container.childNodes.forEach(node => {
                                if (foundCheckbox && node.nodeType === 3 && node.textContent.trim()) {
                                    text += node.textContent.trim();
                                }
                                if (node === checkbox) {
                                    foundCheckbox = true;
                                }
                            });
                            // 如果没获取到，尝试获取 span 元素中的文本
                            if (!text) {
                                const spans = container.querySelectorAll('span');
                                for (const span of spans) {
                                    const spanText = span.textContent.trim();
                                    if (spanText && spanText.includes('.docx') || spanText.includes('.pdf')) {
                                        text = spanText;
                                        break;
                                    }
                                }
                            }
                        }

                        // 清理文本：去除 more_vert、article 等无关内容
                        text = text.replace(/more_vert/g, '').replace(/article/g, '').trim();
                        // 清理多余的空白和特殊字符
                        text = text.replace(/\s+/g, ' ').replace(/[^\w\s\u4e00-\u9fff.\-()_]/g, '').trim();

                        if (text && (text.includes('.docx') || text.includes('.pdf') || text.includes('.md') || text.includes('.txt'))) {
                            // 去重
                            if (!seen.has(text)) {
                                seen.add(text);
                                sources.push({
                                    name: text,
                                    selected: checkbox ? checkbox.checked : false
                                });
                            }
                        }
                    });

                    return sources;
                }
            """)

            logger.info(f"找到 {len(sources)} 个文档源")
            return sources

        except Exception as e:
            logger.error(f"获取文档源列表失败：{e}")
            return []

    async def remove_all_sources(self) -> bool:
        """
        删除当前 Notebook 中的所有文档源（使用 Remove source 功能）
        逐个删除，确保每个文档都被成功移除

        Returns:
            bool: 是否成功
        """
        logger.info("正在删除所有文档源...")

        try:
            max_iterations = 20  # 最多尝试 20 次
            iteration = 0

            while iteration < max_iterations:
                # 获取当前文档源列表
                sources = await self.get_sources()
                if not sources:
                    logger.info("所有文档源已删除完成")
                    return True

                logger.info(f"当前有 {len(sources)} 个文档源，继续删除...")

                # 删除第一个文档源
                removed = await self._remove_single_source()
                if not removed:
                    logger.warning("无法删除文档源，尝试其他方式...")

                # 等待删除完成
                await asyncio.sleep(5)

                iteration += 1

            # 检查最终结果
            final_sources = await self.get_sources()
            if not final_sources:
                logger.info("所有文档源已删除完成")
                return True
            else:
                logger.warning(f"删除后仍剩余 {len(final_sources)} 个文档源")
                return False

        except Exception as e:
            logger.error(f"删除文档源失败：{e}")
            return False

    async def _remove_single_source(self) -> bool:
        """
        删除单个文档源（第一个）
        使用 JavaScript 直接定位和点击

        Returns:
            bool: 是否成功
        """
        try:
            # 先尝试获取页面中所有可能的文档源相关元素结构
            debug_info = await self.page.evaluate("""
                () => {
                    const result = {
                        single_containers: document.querySelectorAll('.single-source-container').length,
                        all_source_like: document.querySelectorAll('[class*="source"]').length,
                        list_items: document.querySelectorAll('[role="listitem"]').length,
                        all_buttons: document.querySelectorAll('button').length
                    };
                    return result;
                }
            """)

            logger.info(f"页面元素统计：{debug_info}")

            # 使用 JavaScript 直接找到第一个文档源并点击其更多按钮
            result = await self.page.evaluate("""
                () => {
                    // 找到所有文档源容器
                    const containers = document.querySelectorAll('.single-source-container');
                    if (containers.length === 0) {
                        console.log('未找到文档源容器');
                        return false;
                    }

                    // 获取第一个容器
                    const firstContainer = containers[0];
                    const text = firstContainer.textContent;
                    console.log('准备删除文档:', text);

                    // 查找容器内的更多按钮（通常是三点图标按钮）
                    let moreBtn = null;

                    // 尝试多种策略查找更多按钮
                    // 1. 查找 aria-label 包含 "More" 的按钮
                    moreBtn = firstContainer.querySelector('button[aria-label*="ore"], button[aria-label*="More"]');

                    // 2. 查找 data-icon 为 more-vert 的按钮
                    if (!moreBtn) {
                        moreBtn = firstContainer.querySelector('[data-icon="more-vert"]');
                    }

                    // 3. 查找包含 more_vert 图标的按钮
                    if (!moreBtn) {
                        const matIcons = firstContainer.querySelectorAll('mat-icon');
                        for (const icon of matIcons) {
                            if (icon.textContent.includes('more_vert')) {
                                moreBtn = icon.parentElement || icon;
                                break;
                            }
                        }
                    }

                    // 4. 查找容器内的最后一个按钮（通常是更多按钮）
                    if (!moreBtn) {
                        const buttons = firstContainer.querySelectorAll('button');
                        if (buttons.length > 0) {
                            moreBtn = buttons[buttons.length - 1];
                        }
                    }

                    if (moreBtn) {
                        console.log('找到更多按钮');
                        moreBtn.click();
                        return true;
                    } else {
                        console.log('未找到更多按钮');
                        return false;
                    }
                }
            """)

            if not result:
                logger.warning("未找到更多按钮，尝试其他方式...")
                return False

            # 等待菜单出现
            await asyncio.sleep(2)

            # 点击删除选项
            return await self._click_delete_option()

        except Exception as e:
            logger.debug(f"删除单个文档源失败：{e}")
            return False

    async def _click_delete_option(self) -> bool:
        """
        在弹出的菜单中点击删除选项

        Returns:
            bool: 是否成功
        """
        try:
            # 等待菜单出现
            await asyncio.sleep(1)

            # 使用 JavaScript 点击删除选项
            result = await self.page.evaluate("""
                () => {
                    // 在弹出菜单中查找删除选项
                    const allText = document.body.textContent;

                    // 查找所有可能的菜单项
                    const menuItems = document.querySelectorAll(
                        '[role="menuitem"], button[role="menuitem"], ' +
                        'button[class*="mat-mdc-menu-item"], ' +
                        '.mat-mdc-menu-item, ' +
                        'button[class*="mdc-menu"], ' +
                        'div[role="menuitem"], ' +
                        'a[role="menuitem"]'
                    );

                    console.log('找到的菜单项数量:', menuItems.length);

                    for (const item of menuItems) {
                        const text = item.textContent.toLowerCase();
                        console.log('检查菜单项:', text.substring(0, 50));
                        if (text.includes('remove') || text.includes('删除') || text.includes('移除')) {
                            console.log('找到删除选项:', text);
                            item.click();
                            return true;
                        }
                    }

                    // 备用：查找所有按钮
                    const buttons = document.querySelectorAll('button');
                    console.log('找到的按钮数量:', buttons.length);
                    for (const btn of buttons) {
                        const text = btn.textContent.toLowerCase();
                        if (text.includes('remove') || text.includes('删除') || text.includes('移除')) {
                            console.log('找到删除按钮:', text);
                            btn.click();
                            return true;
                        }
                    }

                    console.log('未找到删除选项');
                    return false;
                }
            """)

            if result:
                logger.debug("已点击删除选项")
                # 等待确认对话框出现
                await asyncio.sleep(3)

                # 处理确认对话框
                confirm_result = await self._handle_confirm_dialog()
                if confirm_result:
                    logger.debug("已确认删除")
                    await asyncio.sleep(3)

                return True

            logger.warning("未找到删除选项")
            return False

        except Exception as e:
            logger.debug(f"点击删除选项失败：{e}")
            return False

    async def _handle_confirm_dialog(self) -> bool:
        """
        处理确认对话框

        Returns:
            bool: 是否成功点击确认
        """
        try:
            # 尝试多种选择器查找确认按钮
            confirm_result = await self.page.evaluate("""
                () => {
                    // 查找所有按钮
                    const allButtons = document.querySelectorAll('button');
                    console.log('找到的总按钮数量:', allButtons.length);

                    // 查找对话框中的按钮（通常在 cdk-overlay 或 mat-dialog 中）
                    const dialogButtons = document.querySelectorAll(
                        '.cdk-overlay-pane button, ' +
                        '.mat-mdc-dialog-pane button, ' +
                        '[role="dialog"] button, ' +
                        'div[class*="dialog"] button, ' +
                        'div[class*="modal"] button'
                    );
                    console.log('对话框中的按钮数量:', dialogButtons.length);

                    // 优先处理对话框中的按钮
                    for (const btn of dialogButtons) {
                        const text = btn.textContent.toLowerCase().trim();
                        console.log('检查对话框按钮:', text);
                        // 点击确认/删除按钮（通常是红色的那个）
                        if (text.includes('remove') || text.includes('delete') ||
                            text.includes('确认') || text.includes('确定') ||
                            text.includes('yes') || text.includes('ok')) {
                            console.log('点击确认按钮:', text);
                            btn.click();
                            return true;
                        }
                    }

                    // 备用：在所有按钮中查找
                    for (const btn of allButtons) {
                        const text = btn.textContent.toLowerCase().trim();
                        console.log('检查全局按钮:', text);
                        if (text.includes('remove') || text.includes('delete') ||
                            text.includes('确认') || text.includes('确定') ||
                            text.includes('yes') || text.includes('ok')) {
                            console.log('点击确认按钮:', text);
                            btn.click();
                            return true;
                        }
                    }

                    console.log('未找到确认按钮');
                    return false;
                }
            """)

            return confirm_result

        except Exception as e:
            logger.debug(f"处理确认对话框失败：{e}")
            return False

    async def select_sources(self, source_names: List[str]) -> bool:
        """
        选择指定的文档源（用于限定 AI 回答范围）
        取消未选中文档的勾选，只保留指定的文档

        Args:
            source_names: 要选择的文档名称列表

        Returns:
            bool: 是否成功
        """
        logger.info(f"选择文档源：{source_names}")

        try:
            # 使用 JavaScript 直接在 sources 面板中操作 checkbox
            await self.page.evaluate("""
                (sourceNames) => {
                    const sources = [];

                    // 获取所有 single-source-container 元素（包含 checkbox 和文档名）
                    document.querySelectorAll('.single-source-container').forEach(container => {
                        const text = container.textContent;
                        const checkbox = container.querySelector('input[type="checkbox"]');
                        if (text && (text.includes('.docx') || text.includes('.pdf') || text.includes('.md') || text.includes('.txt')) && checkbox) {
                            sources.push({
                                text: text,
                                checkbox: checkbox,
                                checked: checkbox.checked
                            });
                        }
                    });

                    // 遍历所有文档，设置正确的选中状态
                    for (const source of sources) {
                        const shouldSelect = sourceNames.some(name => source.text.includes(name));
                        const isChecked = source.checked;

                        // 需要选中但没选中，或者需要取消但已选中
                        if (shouldSelect !== isChecked) {
                            source.checkbox.click();
                        }
                    }
                }
            """, source_names)

            # 等待 UI 更新
            await asyncio.sleep(2)

            # 从 UI 获取实际的引用源数量（使用 XPath）
            source_count_text = await self.page.evaluate("""
                () => {
                    const xpathResult = document.evaluate(
                        '/html/body/labs-tailwind-root/div/notebook/div/section[2]/chat-panel/omnibar/div/div/div/query-box/div/div/form/div/div/div',
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    );
                    const el = xpathResult.singleNodeValue;
                    if (el) {
                        return el.textContent?.trim() || '';
                    }
                    return '';
                }
            """)

            logger.info(f"引用源显示：{source_count_text}")
            return True

        except Exception as e:
            logger.error(f"选择文档源失败：{e}")
            return False

    async def ask_question_with_sources(
        self,
        question: str,
        source_names: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        提问并指定参考的文档源

        Args:
            question: 问题文本
            source_names: 要选择的文档名称列表（可选）

        Returns:
            AI 回答或 None
        """
        # 先选择文档源（如果有指定）
        if source_names:
            await self.select_sources(source_names)

        # 然后在问题中明确指定文档
        if source_names:
            # 在问题前添加文档限定
            source_text = ", ".join(source_names)
            full_question = f"根据以下文档：{source_text}。{question}"
        else:
            full_question = question

        return await self.ask_question(full_question)

    async def navigate_to_notebook(self, notebook_name: str) -> bool:
        """
        导航到指定名称的 Notebook

        Args:
            notebook_name: Notebook 名称

        Returns:
            bool: 是否成功
        """
        logger.info(f"导航到 Notebook: {notebook_name}")

        try:
            # 获取 Notebook 列表
            notebooks = await self.get_notebooks()

            for nb in notebooks:
                if notebook_name.lower() in nb["name"].lower():
                    return await self.open_notebook(nb["id"])

            logger.warning(f"未找到 Notebook: {notebook_name}")
            return False

        except Exception as e:
            logger.error(f"导航到 Notebook 失败：{e}")
            return False


async def main():
    """测试入口"""
    config = {
        "headless": False,
        "page_timeout": 60000,
        "upload_timeout": 300,
        "processing_timeout": 600,
        "request_interval": 3000,
    }

    client = NotebookLMClient(config)
    await client.launch_browser()

    try:
        # 测试登录
        if await client.login():
            print("登录成功!")

            # 测试获取 Notebook 列表
            notebooks = await client.get_notebooks()
            print(f"Notebooks: {notebooks}")

        else:
            print("登录失败")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
