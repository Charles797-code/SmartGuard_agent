"""
邮件监控服务
定时检查邮箱，发现可疑邮件自动进行反诈检测
"""

import asyncio
import time
import uuid
import base64
import hashlib
import re
import imaplib
import email
from email.header import decode_header
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.data.database import get_database


class EmailMonitorService:
    """
    邮件监控服务
    
    功能：
    1. 定时轮询邮箱（IMAP协议）
    2. 检测可疑邮件（LLM智能分析 + 关键词匹配）
    3. 生成风险评分和预警
    4. 保存检测记录到数据库
    """
    
    IMAP_SERVERS = {
        "qq": {"host": "imap.qq.com", "port": 993, "ssl": True},
        "qqmail": {"host": "imap.qq.com", "port": 993, "ssl": True},
        "gmail": {"host": "imap.gmail.com", "port": 993, "ssl": True},
        "163": {"host": "imap.163.com", "port": 993, "ssl": True},
        "126": {"host": "imap.126.com", "port": 993, "ssl": True},
        "outlook": {"host": "outlook.office365.com", "port": 993, "ssl": True},
        "tom": {"host": "imap.tom.com", "port": 993, "ssl": True},
        "sina": {"host": "imap.sina.com", "port": 993, "ssl": True},
    }
    
    SCAM_KEYWORDS = {
        "extreme_risk": [
            "账户异常", "资金被冻结", "银行卡冻结", "信用卡冻结",
            "涉嫌洗钱", "刑事案件", "通缉令", "逮捕令",
            "安全账户", "转账至安全账户", "验证资金",
            "您的快递", "藏毒包裹", "海关扣押",
        ],
        "high_risk": [
            "刷单", "返利", "做任务", "佣金", "垫付",
            "高收益", "稳赚不赔", "内幕消息", "投资理财",
            "无抵押贷款", "快速放款", "征信问题",
            "退款", "理赔", "补偿", "双倍赔偿",
            "中奖", "领取奖金", "奖品", "抽奖",
            "博彩", "彩票", "下注", "导师带单",
            "比特币", "数字货币", "区块链投资",
        ],
        "medium_risk": [
            "限时优惠", "最后机会", "名额有限", "立即行动",
            "身份证", "验证码", "密码", "安全码",
            "链接", "点击此处", "打开链接", "扫码",
            "优惠码", "兑换码", "激活码",
            "客服热线", "人工服务", "联系我们",
        ],
    }
    
    SCAM_PATTERNS = [
        {"name": "制造紧迫感", "patterns": ["立即", "马上", "限时", "截止", "紧急", "24小时", "今日"]},
        {"name": "威胁恐吓", "patterns": ["冻结", "起诉", "坐牢", "逮捕", "黑名单", "追究"]},
        {"name": "要求转账", "patterns": ["转账", "汇款", "付款", "扫码支付", "押金"]},
        {"name": "索要验证码", "patterns": ["验证码", "安全码", "动态密码", "登录密码"]},
        {"name": "先给甜头", "patterns": ["先返", "首单", "首次", "体验金", "赠送"]},
    ]
    
    def __init__(self):
        self.db = get_database()
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._llm_client = None
    
    def _get_llm_client(self):
        """获取LLM客户端"""
        if self._llm_client is None:
            try:
                from src.modules.llm import create_qwen_client
                from dotenv import load_dotenv
                load_dotenv()
                import os
                api_key = os.getenv("DASHSCOPE_API_KEY")
                model = os.getenv("QWEN_MODEL", "qwen-turbo")
                if api_key:
                    self._llm_client = create_qwen_client(api_key=api_key, model=model)
            except Exception as e:
                print(f"[EmailMonitor] LLM初始化失败: {e}")
                self._llm_client = None
        return self._llm_client
    
    def _encrypt_password(self, password: str) -> str:
        """简单加密密码"""
        return base64.b64encode(password.encode()).decode()
    
    def _decrypt_password(self, encrypted: str) -> str:
        """解密密码"""
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except:
            return ""
    
    def _detect_imap_server(self, email_address: str) -> Dict[str, Any]:
        """根据邮箱地址推断IMAP服务器"""
        domain = email_address.split("@")[-1].lower()
        
        if "qq" in domain:
            return self.IMAP_SERVERS["qq"]
        elif "gmail" in domain:
            return self.IMAP_SERVERS["gmail"]
        elif "163" in domain:
            return self.IMAP_SERVERS["163"]
        elif "126" in domain:
            return self.IMAP_SERVERS["126"]
        elif "outlook" in domain or "hotmail" in domain:
            return self.IMAP_SERVERS["outlook"]
        else:
            return self.IMAP_SERVERS["qq"]
    
    def _decode_email_header(self, encoded_str: str) -> str:
        """解码邮件标题"""
        if not encoded_str:
            return ""
        decoded_parts = decode_header(encoded_str)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    result.append(part.decode(encoding or 'utf-8', errors='replace'))
                except:
                    result.append(part.decode('utf-8', errors='replace'))
            else:
                result.append(part)
        return ''.join(result)
    
    def _get_email_body(self, msg) -> str:
        """获取邮件正文"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset, errors='replace')
                        break
                    except:
                        pass
                elif content_type == "text/html" and not body:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset, errors='replace')
                    except:
                        pass
        else:
            try:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset, errors='replace')
            except:
                pass
        
        body = re.sub(r'<[^>]+>', ' ', body)
        body = re.sub(r'\s+', ' ', body)
        return body.strip()
    
    async def _analyze_with_llm(self, subject: str, body: str, sender: str) -> Dict[str, Any]:
        """
        使用LLM分析邮件内容
        
        Returns:
            LLM分析结果
        """
        llm_client = self._get_llm_client()
        
        if not llm_client or not llm_client.is_available:
            # LLM不可用时使用规则匹配
            return self._analyze_with_rules(subject, body, sender)
        
        system_prompt = """你是邮件安全分析专家，负责分析邮件内容并判断是否存在诈骗风险。

分析要求：
1. 仔细阅读邮件标题、正文、发件人信息
2. 识别常见的诈骗手法：冒充客服、钓鱼链接、虚假中奖、投资理财、冒充公检法等
3. 分析邮件的整体意图和可疑程度
4. 结合上下文判断是否为诈骗邮件

回复格式（必须严格遵守）：
[分析内容...]
- 邮件类型: <正常邮件/诈骗邮件>
- 风险等级: <0-5，0=安全，5=极危>
- 风险类型: <normal/police_impersonation/investment_fraud/phishing/scam_other等>
- 可疑特征: <发现的可疑点，用逗号分隔>

请给出专业的分析结果："""

        user_message = f"""邮件标题: {subject}
发件人: {sender}
邮件正文: {body[:2000]}"""  # 限制正文长度
        
        try:
            messages = [{"role": "user", "content": user_message}]
            response = await llm_client.chat(messages, system_prompt=system_prompt)
            
            # 解析LLM返回的结果
            risk_level = 0
            risk_type = "normal"
            analysis = ""
            detected_keywords = []
            
            # 提取风险等级
            level_match = re.search(r'风险等级:\s*(\d+)', response)
            if level_match:
                risk_level = int(level_match.group(1))
            
            # 提取风险类型
            type_match = re.search(r'风险类型:\s*(\w+)', response)
            if type_match:
                risk_type = type_match.group(1)
            
            # 提取分析内容
            analysis_match = re.search(r'\[分析内容\.\.\.\](.*?)(?=\[|$)', response, re.DOTALL)
            if analysis_match:
                analysis = analysis_match.group(1).strip()
            
            # 提取可疑特征
            features_match = re.search(r'可疑特征:\s*(.+?)(?:\n|$)', response)
            if features_match:
                features = features_match.group(1)
                detected_keywords = [k.strip() for k in features.split(',') if k.strip()]
            
            # 计算风险评分
            scam_score = min(risk_level / 5.0, 1.0)
            
            return {
                "scam_score": scam_score,
                "risk_level": risk_level,
                "risk_type": risk_type,
                "analysis": analysis,
                "detected_keywords": detected_keywords,
                "detected_patterns": [],
                "method": "llm"
            }
            
        except Exception as e:
            print(f"[EmailMonitor] LLM分析失败: {e}")
            return self._analyze_with_rules(subject, body, sender)
    
    def _analyze_with_rules(self, subject: str, body: str, sender: str) -> Dict[str, Any]:
        """使用规则分析邮件"""
        combined_text = f"{subject} {body} {sender}".lower()
        
        detected_keywords = []
        detected_patterns = []
        risk_score = 0.0
        
        for level, keywords in self.SCAM_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    detected_keywords.append({
                        "keyword": keyword,
                        "level": level
                    })
                    if level == "extreme_risk":
                        risk_score += 0.4
                    elif level == "high_risk":
                        risk_score += 0.25
                    elif level == "medium_risk":
                        risk_score += 0.1
        
        for pattern_info in self.SCAM_PATTERNS:
            for pattern in pattern_info["patterns"]:
                if pattern.lower() in combined_text:
                    detected_patterns.append(pattern_info["name"])
                    risk_score += 0.15
                    break
        
        risk_score = min(risk_score, 1.0)
        
        if risk_score >= 0.7:
            risk_level = 5
        elif risk_score >= 0.4:
            risk_level = 3
        elif risk_score >= 0.2:
            risk_level = 2
        else:
            risk_level = 0
        
        return {
            "scam_score": risk_score,
            "risk_level": risk_level,
            "risk_type": self._guess_risk_type(combined_text),
            "analysis": f"规则分析发现{len(detected_keywords)}个关键词，{len(detected_patterns)}种模式",
            "detected_keywords": detected_keywords,
            "detected_patterns": list(set(detected_patterns)),
            "method": "rules"
        }
    
    def _guess_risk_type(self, text: str) -> str:
        """根据内容猜测风险类型"""
        if any(k in text for k in ["公安", "警察", "检察院", "法院", "通缉", "洗钱"]):
            return "police_impersonation"
        if any(k in text for k in ["投资", "理财", "高收益", "稳赚"]):
            return "investment_fraud"
        if any(k in text for k in ["刷单", "兼职", "佣金"]):
            return "part_time_fraud"
        if any(k in text for k in ["钓鱼", "链接", "登录", "账户异常"]):
            return "phishing"
        if any(k in text for k in ["中奖", "奖品", "领取"]):
            return "prize_fraud"
        return "scam_other"
    
    async def _analyze_email(self, subject: str, body: str, sender: str) -> Dict[str, Any]:
        """分析邮件（优先使用LLM）"""
        return await self._analyze_with_llm(subject, body, sender)
    
    async def add_email_config(
        self,
        user_id: str,
        email_address: str,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """添加邮件监控配置"""
        imap_info = self._detect_imap_server(email_address)
        
        config_id = f"emc_{uuid.uuid4().hex[:12]}"
        now = time.time()
        
        config = {
            "id": config_id,
            "user_id": user_id,
            "email_address": email_address,
            "imap_host": imap_info["host"],
            "imap_port": imap_info["port"],
            "username": username or email_address,
            "password_encrypted": self._encrypt_password(password),
            "use_ssl": 1 if imap_info["ssl"] else 0,
            "check_interval": 300,
            "is_active": 1,
            "last_check_status": "never",
            "created_at": now,
            "updated_at": now
        }
        
        await self.db.insert("email_monitor_configs", config)
        await self.start_monitoring(config_id)
        
        return {
            "success": True,
            "config_id": config_id,
            "message": f"邮件监控已配置完成，每5分钟自动检测一次",
            "imap_server": imap_info["host"]
        }
    
    async def remove_email_config(self, config_id: str, user_id: str) -> bool:
        """移除邮件监控配置"""
        await self.stop_monitoring(config_id)
        
        configs = await self.db.query("email_monitor_configs", {
            "id": config_id,
            "user_id": user_id
        }, limit=1)
        
        if configs:
            await self.db.delete("email_monitor_configs", config_id)
            return True
        return False
    
    async def get_user_configs(self, user_id: str) -> List[Dict]:
        """获取用户的所有邮件监控配置"""
        configs = await self.db.query("email_monitor_configs", {
            "user_id": user_id
        })
        
        result = []
        for config in configs:
            result.append({
                "id": config["id"],
                "email_address": config["email_address"],
                "imap_host": config["imap_host"],
                "imap_port": config["imap_port"],
                "is_active": bool(config.get("is_active", 1)),
                "check_interval": config.get("check_interval", 300),
                "last_check_at": config.get("last_check_at"),
                "last_check_status": config.get("last_check_status", "never"),
                "created_at": config.get("created_at")
            })
        
        return result
    
    async def update_config_status(self, config_id: str, status: str):
        """更新配置状态"""
        await self.db.update("email_monitor_configs", config_id, {
            "id": config_id,
            "last_check_status": status,
            "last_check_at": time.time()
        })
    
    async def _fetch_and_analyze_emails(self, config: Dict) -> List[Dict]:
        """获取并分析邮件"""
        results = []
        
        try:
            password = self._decrypt_password(config["password_encrypted"])
            
            if config.get("use_ssl"):
                mail = imaplib.IMAP4_SSL(config["imap_host"], config["imap_port"])
            else:
                mail = imaplib.IMAP4(config["imap_host"], config["imap_port"])
            
            mail.login(config["username"], password)
            mail.select("INBOX")
            
            import datetime
            date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%d-%b-%Y")
            _, messages = mail.search(None, f'SINCE {date} UNSEEN')
            
            mail_ids = messages[0].split()
            
            for mail_id in mail_ids:
                try:
                    _, msg_data = mail.fetch(mail_id, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    subject = self._decode_email_header(msg.get("Subject", ""))
                    sender = self._decode_email_header(msg.get("From", ""))
                    date_str = msg.get("Date", "")
                    body = self._get_email_body(msg)
                    
                    email_date = 0
                    try:
                        from email.utils import parsedate_to_datetime
                        email_date = parsedate_to_datetime(date_str).timestamp()
                    except:
                        email_date = time.time()
                    
                    existing = await self.db.query("email_monitor_logs", {
                        "config_id": config["id"],
                        "email_subject": subject[:100]
                    }, limit=1)
                    
                    if existing:
                        continue
                    
                    # 使用LLM分析邮件
                    analysis = await self._analyze_email(subject, body, sender)
                    
                    log_id = f"eml_{uuid.uuid4().hex[:12]}"
                    
                    log_entry = {
                        "id": log_id,
                        "config_id": config["id"],
                        "user_id": config["user_id"],
                        "email_subject": subject[:500],
                        "email_from": sender[:200],
                        "email_date": email_date,
                        "scam_score": analysis["scam_score"],
                        "risk_level": str(analysis["risk_level"]),
                        "detected_keywords": __import__('json').dumps(analysis["detected_keywords"], ensure_ascii=False),
                        "detected_patterns": __import__('json').dumps(analysis["detected_patterns"], ensure_ascii=False),
                        "status": "detected" if analysis["scam_score"] >= 0.2 else "safe",
                        "is_read": 0,
                        "created_at": time.time()
                    }
                    
                    await self.db.insert("email_monitor_logs", log_entry)
                    
                    # 返回高风险以上的检测结果
                    if analysis["scam_score"] >= 0.2:
                        results.append({
                            "log_id": log_id,
                            "subject": subject,
                            "sender": sender,
                            "scam_score": analysis["scam_score"],
                            "risk_level": analysis["risk_level"],
                            "risk_type": analysis.get("risk_type", "unknown"),
                            "analysis": analysis.get("analysis", ""),
                            "keywords": analysis["detected_keywords"],
                            "patterns": analysis["detected_patterns"]
                        })
                
                except Exception as e:
                    print(f"处理邮件失败: {e}")
                    continue
            
            mail.store(mail_ids[-1] if mail_ids else b'1', '+FLAGS', '\\Seen')
            mail.logout()
            
            await self.update_config_status(config["id"], "success")
            
        except Exception as e:
            print(f"获取邮件失败: {e}")
            await self.update_config_status(config["id"], f"error: {str(e)}")
        
        return results
    
    async def start_monitoring(self, config_id: str):
        """启动对指定配置的监控"""
        if config_id in self._monitoring_tasks:
            return
        
        config = await self.db.query("email_monitor_configs", {"id": config_id}, limit=1)
        if not config:
            return
        
        config = config[0]
        if not config.get("is_active"):
            return
        
        task = asyncio.create_task(self._monitor_loop(config))
        self._monitoring_tasks[config_id] = task
        self._running = True
    
    async def stop_monitoring(self, config_id: str):
        """停止对指定配置的监控"""
        if config_id in self._monitoring_tasks:
            self._monitoring_tasks[config_id].cancel()
            del self._monitoring_tasks[config_id]
        
        if not self._monitoring_tasks:
            self._running = False
    
    async def _monitor_loop(self, config: Dict):
        """监控循环"""
        interval = config.get("check_interval", 300)
        
        asyncio.create_task(self._fetch_and_analyze_emails(config))
        while True:
            try:
                await self._fetch_and_analyze_emails(config)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"监控出错: {e}")
            
            await asyncio.sleep(interval)
    
    async def start_all_monitoring(self):
        """启动所有活跃的监控配置"""
        configs = await self.db.query("email_monitor_configs", {"is_active": 1})
        
        for config in configs:
            await self.start_monitoring(config["id"])
    
    async def stop_all_monitoring(self):
        """停止所有监控"""
        for config_id in list(self._monitoring_tasks.keys()):
            await self.stop_monitoring(config_id)
    
    async def get_user_alerts(self, user_id: str, limit: int = 50) -> List[Dict]:
        """获取用户的邮件监控预警"""
        logs = await self.db.query("email_monitor_logs", {"user_id": user_id})
        
        logs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        result = []
        for log in logs[:limit]:
            result.append({
                "id": log["id"],
                "subject": log["email_subject"],
                "sender": log["email_from"],
                "email_date": log["email_date"],
                "scam_score": log["scam_score"],
                "risk_level": log["risk_level"],
                "keywords": __import__('json').loads(log.get("detected_keywords", "[]")),
                "patterns": __import__('json').loads(log.get("detected_patterns", "[]")),
                "status": log.get("status"),
                "is_read": bool(log.get("is_read", 0)),
                "created_at": log.get("created_at")
            })
        
        return result
    
    async def mark_alert_read(self, log_id: str, user_id: str):
        """标记预警为已读"""
        await self.db.update("email_monitor_logs", log_id, {
            "id": log_id,
            "is_read": 1
        })
    
    async def get_unread_alert_count(self, user_id: str) -> int:
        """获取未读预警数量"""
        logs = await self.db.query("email_monitor_logs", {
            "user_id": user_id,
            "is_read": 0
        })
        return len(logs)


# 全局实例
email_monitor_service = EmailMonitorService()
