"""
poe2_time_check - AstrBot 插件
流放之路2 (Path of Exile 2) 服务器时间查询插件

功能：
- 查询国际服和腾讯国服的开服时间、服务器状态
- 支持多指令触发：/poe2、/流放之路2、/poe2时间
- 本地缓存机制，避免频繁请求
- 完善的错误处理和容错机制
"""

import asyncio
import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger

# 北京时间时区
BJT = timezone(timedelta(hours=8))


class Poe2TimeCheck(Star):
    """流放之路2服务器时间查询插件"""

    def __init__(self, context: Context):
        super().__init__(context)
        
        # 默认配置
        self.cache_duration = 600  # 缓存时长（秒），默认10分钟
        self.request_timeout = 15  # 请求超时时间（秒）
        
        # 数据源URL
        self.us_url = "https://poe2db.tw/us/"
        self.cn_url = "https://poe2db.tw/cn/"
        
        # 缓存数据
        self._cache = {
            "us": {"data": None, "timestamp": 0},
            "cn": {"data": None, "timestamp": 0}
        }
        
        # 加载自定义配置
        self._load_config()
        
        logger.info("[poe2_time_check] 插件已加载")

    def _load_config(self):
        """加载插件配置"""
        try:
            config = self.context.get_config()
            if config:
                plugin_config = config.get("poe2_time_check", {})
                self.cache_duration = plugin_config.get("cache_duration", 600)
                self.request_timeout = plugin_config.get("request_timeout", 15)
                logger.info(f"[poe2_time_check] 配置已加载: 缓存{self.cache_duration}秒, 超时{self.request_timeout}秒")
        except Exception as e:
            logger.warning(f"[poe2_time_check] 加载配置失败，使用默认配置: {e}")

    def _get_cache(self, server_type: str) -> Optional[dict]:
        """获取缓存数据，如果过期则返回None"""
        cache_entry = self._cache.get(server_type)
        if cache_entry and cache_entry["data"]:
            if time.time() - cache_entry["timestamp"] < self.cache_duration:
                logger.debug(f"[poe2_time_check] 使用{server_type}缓存数据")
                return cache_entry["data"]
        return None

    def _set_cache(self, server_type: str, data: dict):
        """设置缓存数据"""
        self._cache[server_type] = {
            "data": data,
            "timestamp": time.time()
        }
        logger.debug(f"[poe2_time_check] 已更新{server_type}缓存")

    async def _fetch_page(self, url: str) -> Optional[str]:
        """
        异步获取网页内容
        
        使用 httpx 异步库获取页面 HTML，包含超时和错误处理
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                return response.text
        except httpx.TimeoutException:
            logger.error(f"[poe2_time_check] 请求超时: {url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"[poe2_time_check] 网络请求失败: {url}, 错误: {e}")
            return None

    def _timestamp_to_datetime(self, ts: str) -> str:
        """将Unix时间戳转换为北京时间字符串"""
        try:
            dt = datetime.fromtimestamp(int(ts), tz=BJT)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):
            return ""

    def _calc_countdown(self, target_ts: str) -> str:
        """计算倒计时"""
        try:
            target = datetime.fromtimestamp(int(target_ts), tz=BJT)
            now = datetime.now(BJT)
            diff = target - now
            
            if diff.total_seconds() <= 0:
                return "已开始"
            
            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        except (ValueError, OSError):
            return ""

    def _parse_page(self, html: str, server_name: str) -> dict:
        """
        解析页面数据（通用方法）
        
        HTML结构：
        <div class="card mb-2">
          <h5>赛季名称 0.5</h5>
          <div class="row">
            <div class="col text-center">
              <div data-displaytime="1780624800"></div>
              <div><a href="...">开始倒数</a></div>
              <div data-countdown="1780624800" data-format="day"></div>
            </div>
          </div>
        </div>
        
        注意：文本内容是空的，需要从属性值计算
        """
        result = {
            "server_name": server_name,
            "events": [],
            "parse_time": datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "unknown"
        }
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 通过 data-displaytime 属性查找
            time_divs = soup.find_all("div", attrs={"data-displaytime": True})
            
            for time_div in time_divs:
                event_info = {}
                
                # 从属性值获取时间戳并转换为日期
                ts = time_div.get("data-displaytime", "")
                if ts:
                    event_info["date"] = self._timestamp_to_datetime(ts)
                
                # 查找同级的倒计时元素（在同一个 col text-center 容器中）
                parent = time_div.parent
                if parent:
                    countdown_div = parent.find("div", attrs={"data-countdown": True})
                    if countdown_div:
                        target_ts = countdown_div.get("data-countdown", "")
                        if target_ts:
                            event_info["countdown"] = self._calc_countdown(target_ts)
                    
                    # 查找状态链接
                    status_link = parent.find("a")
                    if status_link:
                        status_text = status_link.get_text(strip=True)
                        if not status_text:
                            # 链接文本为空，根据时间戳判断状态
                            if ts:
                                target = datetime.fromtimestamp(int(ts), tz=BJT)
                                now = datetime.now(BJT)
                                if target > now:
                                    event_info["status"] = "即将开始"
                                    result["status"] = "upcoming"
                                else:
                                    event_info["status"] = "进行中"
                                    result["status"] = "running"
                        elif "开始倒数" in status_text or "Starts in" in status_text:
                            event_info["status"] = "即将开始"
                            result["status"] = "upcoming"
                        elif "已运行" in status_text:
                            event_info["status"] = "进行中"
                            result["status"] = "running"
                
                # 向上查找 h5 赛季名称（需要到 card mb-2 层）
                container = time_div
                for _ in range(6):
                    if container.parent:
                        container = container.parent
                        h5 = container.find("h5")
                        if h5:
                            h5_text = h5.get_text(strip=True)
                            if h5_text:
                                event_info["name"] = h5_text
                                break
                
                if "name" not in event_info:
                    event_info["name"] = "未知赛季"
                
                if event_info.get("date"):
                    result["events"].append(event_info)
            
            logger.info(f"[poe2_time_check] {server_name}解析完成，找到 {len(result['events'])} 个事件")
            
        except Exception as e:
            logger.error(f"[poe2_time_check] 解析{server_name}页面失败: {e}")
            result["parse_error"] = str(e)
        
        return result

    async def _get_server_data(self, server_type: str) -> dict:
        """
        获取服务器数据（带缓存）
        
        Args:
            server_type: 服务器类型，'us' 或 'cn'
        
        Returns:
            解析后的服务器数据字典
        """
        # 检查缓存
        cached = self._get_cache(server_type)
        if cached:
            return cached
        
        # 获取页面数据
        url = self.us_url if server_type == "us" else self.cn_url
        server_name = "国际服" if server_type == "us" else "腾讯国服"
        html = await self._fetch_page(url)
        
        if not html:
            return {
                "server_name": server_name,
                "events": [],
                "status": "error",
                "error": "无法获取页面数据，请检查网络连接"
            }
        
        # 解析页面
        data = self._parse_page(html, server_name)
        
        # 更新缓存
        self._set_cache(server_type, data)
        
        return data

    def _format_response(self, us_data: dict, cn_data: dict) -> str:
        """
        格式化回复消息
        
        将国际服和国服数据整理成清晰的文本格式
        """
        lines = []
        lines.append("=" * 30)
        lines.append("🎮 流放之路2 服务器状态")
        lines.append("=" * 30)
        lines.append("")
        
        # 国际服信息
        lines.append("🌍 【国际服】")
        lines.append("-" * 20)
        if us_data.get("events"):
            for event in us_data["events"]:
                lines.append(f"📌 {event.get('name', '未知')}")
                if event.get("date"):
                    lines.append(f"⏰ 时间: {event['date']}")
                if event.get("status"):
                    lines.append(f"📊 状态: {event['status']}")
                if event.get("countdown"):
                    lines.append(f"⏳ 倒计时: {event['countdown']}")
                lines.append("")
        elif us_data.get("error"):
            lines.append(f"❌ {us_data['error']}")
        else:
            lines.append("暂无活动信息")
        lines.append("")
        
        # 国服信息
        lines.append("🇨🇳 【腾讯国服】")
        lines.append("-" * 20)
        if cn_data.get("events"):
            for event in cn_data["events"]:
                lines.append(f"📌 {event.get('name', '未知')}")
                if event.get("date"):
                    lines.append(f"⏰ 时间: {event['date']}")
                if event.get("status"):
                    lines.append(f"📊 状态: {event['status']}")
                if event.get("countdown"):
                    lines.append(f"⏳ 倒计时: {event['countdown']}")
                lines.append("")
        elif cn_data.get("error"):
            lines.append(f"❌ {cn_data['error']}")
        else:
            lines.append("暂无活动信息")
        lines.append("")
        
        # 数据更新时间
        parse_time = us_data.get("parse_time") or cn_data.get("parse_time", "")
        if parse_time:
            lines.append(f"🔄 数据更新时间: {parse_time}")
        
        lines.append("=" * 30)
        
        return "\n".join(lines)

    @filter.command("poe2")
    async def cmd_poe2(self, event: AstrMessageEvent):
        """
        /poe2 指令处理
        
        查询流放之路2国际服和国服的服务器时间信息
        """
        yield event.plain_result("正在查询流放之路2服务器状态，请稍候...")
        
        try:
            # 并发获取国际服和国服数据
            us_data, cn_data = await asyncio.gather(
                self._get_server_data("us"),
                self._get_server_data("cn")
            )
            
            # 格式化并返回结果
            response = self._format_response(us_data, cn_data)
            yield event.plain_result(response)
            
        except Exception as e:
            logger.error(f"[poe2_time_check] 查询失败: {e}")
            yield event.plain_result(f"❌ 查询失败: {str(e)}\n请稍后重试或检查网络连接。")

    @filter.command("流放之路2")
    async def cmd_poe2_cn(self, event: AstrMessageEvent):
        """
        /流放之路2 指令处理
        
        与 /poe2 功能相同，提供中文指令入口
        """
        async for result in self.cmd_poe2(event):
            yield result

    @filter.command("poe2时间")
    async def cmd_poe2_time(self, event: AstrMessageEvent):
        """
        /poe2时间 指令处理
        
        与 /poe2 功能相同，提供时间相关指令入口
        """
        async for result in self.cmd_poe2(event):
            yield result

    @filter.command("poe2help")
    async def cmd_poe2_help(self, event: AstrMessageEvent):
        """
        /poe2help 指令处理
        
        显示插件帮助信息
        """
        help_text = """
🎮 流放之路2时间查询插件 - 帮助

📋 可用指令：
• /poe2 - 查询服务器状态
• /流放之路2 - 查询服务器状态（中文）
• /poe2时间 - 查询服务器状态
• /poe2help - 显示此帮助信息

📊 查询内容：
• 国际服 (poe2db.tw/us)
• 腾讯国服 (poe2db.tw/cn)

⏰ 缓存说明：
• 数据缓存时间: {cache_duration}秒
• 避免频繁请求，保护数据源

💡 提示：
同时查询两个服务器的数据，返回开服时间、倒计时和服务器状态信息。
""".format(cache_duration=self.cache_duration)
        
        yield event.plain_result(help_text.strip())

    async def terminate(self):
        """插件卸载/停用时的清理操作"""
        logger.info("[poe2_time_check] 插件已卸载")
