"""
举报服务
处理用户提交的诈骗举报
"""

import time
import json
import asyncio
import secrets
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from src.data.database import get_database


class ReportStatus(Enum):
    PENDING = "pending"      # 待处理
    REVIEWED = "reviewed"   # 已审核
    VERIFIED = "verified"   # 已确认
    REJECTED = "rejected"   # 已驳回
    FORWARDED = "forwarded" # 已转交警方


class ReportSource(Enum):
    USER_SUBMISSION = "user_submission"  # 用户主动举报
    AUTO_DETECTED = "auto_detected"      # 系统自动检测
    LEARNED = "learned"                  # 从举报中学习


@dataclass
class ScamReport:
    """诈骗举报"""
    report_id: str
    user_id: str
    
    # 基本信息
    scam_type: str              # 诈骗类型
    title: str                 # 举报标题
    content: str               # 举报内容（骗子的话术等）
    
    # 联系方式
    scammer_contact: Optional[str] = None      # 骗子联系方式
    scammer_account: Optional[str] = None      # 骗子账号
    
    # 诈骗详情
    platform: Optional[str] = None             # 诈骗平台
    amount: Optional[float] = None              # 涉案金额
    description: Optional[str] = None           # 详细描述
    
    # 附件
    evidence_urls: List[str] = None            # 证据链接
    
    # 状态
    status: str = "pending"
    source: str = "user_submission"
    
    # 进化相关
    extracted_keywords: List[str] = None       # 提取的关键词
    extracted_patterns: List[str] = None       # 提取的模式
    learned: bool = False                      # 是否已学习
    
    # 时间
    created_at: float = 0
    updated_at: float = 0


class ReportService:
    """
    举报服务
    
    功能：
    1. 接收用户举报
    2. 提取诈骗特征（关键词、模式）
    3. 存储举报记录
    4. 接入自进化模块
    """
    
    # 诈骗类型映射
    SCAM_TYPES = {
        "刷单返利": "part_time_fraud",
        "虚假投资": "investment_fraud",
        "杀猪盘": "pig_butchery",
        "冒充公检法": "police_impersonation",
        "冒充客服": "fake_customer",
        "网络贷款": "loan_fraud",
        "退款理赔": "refund_fraud",
        "网络购物": "shopping_fraud",
        "游戏交易": "gaming_fraud",
        "积分兑换": "points_fraud",
        "虚假中奖": "prize_fraud",
        "钓鱼链接": "phishing",
        "其他": "other"
    }
    
    # 关键词模式
    KEYWORD_PATTERNS = {
        "刷单": ["刷单", "返利", "做任务", "佣金", "垫付"],
        "投资": ["投资", "理财", "高收益", "稳赚", "内幕", "漏洞"],
        "杀猪盘": ["博彩", "彩票", "下注", "导师", "带你赚钱"],
        "公检法": ["涉嫌", "犯罪", "通缉", "逮捕", "洗钱", "账户"],
        "客服": ["客服", "退款", "补偿", "订单异常", "卡单"],
        "贷款": ["贷款", "额度", "征信", "无抵押", "先收费"],
        "购物": ["商品", "退款", "快递", "订单", "质量问题"],
    }
    
    def __init__(self):
        self.reports: List[ScamReport] = []
        self._report_counter = 0
        self.db = get_database()
        self._initialized = False
        # 不要在 __init__ 中启动异步任务，会导致事件循环错误
    
    async def initialize(self):
        """初始化服务，在应用启动时调用"""
        if not self._initialized:
            await self._load_reports_from_db()
            self._initialized = True
    
    async def _load_reports_from_db(self):
        """从数据库加载举报数据"""
        try:
            db_reports = await self.db.query("scam_reports", limit=10000)
            for r in db_reports:
                report = ScamReport(
                    report_id=r.get("report_id", ""),
                    user_id=r.get("user_id", ""),
                    scam_type=r.get("scam_type", ""),
                    title=r.get("title", ""),
                    content=r.get("content", ""),
                    scammer_contact=r.get("scammer_contact"),
                    scammer_account=r.get("scammer_account"),
                    platform=r.get("platform"),
                    amount=r.get("amount"),
                    description=r.get("description"),
                    evidence_urls=json.loads(r.get("evidence_urls", "[]")) if r.get("evidence_urls") else [],
                    status=r.get("status", "pending"),
                    source=r.get("source", "user_submission"),
                    extracted_keywords=json.loads(r.get("extracted_keywords", "[]")) if r.get("extracted_keywords") else [],
                    extracted_patterns=json.loads(r.get("extracted_patterns", "[]")) if r.get("extracted_patterns") else [],
                    learned=bool(r.get("learned", 0)),
                    created_at=r.get("created_at", 0),
                    updated_at=r.get("updated_at", 0)
                )
                self.reports.append(report)
        except Exception as e:
            print(f"加载举报数据失败: {e}")
    
    def _generate_report_id(self) -> str:
        self._report_counter += 1
        return f"RPT{int(time.time())}{self._report_counter:04d}"
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        text_lower = text.lower()
        keywords = []
        for category, patterns in self.KEYWORD_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    keywords.append(pattern)
        return list(set(keywords))
    
    def _extract_patterns(self, text: str, scam_type: str) -> List[str]:
        """提取诈骗模式"""
        patterns = []
        
        # 常见模式
        common_patterns = {
            "先给甜头": ["先转", "先返", "先赚", "尝到甜头", "第一笔"],
            "制造紧迫": ["立即", "马上", "限时", "错过", "截止", "紧急"],
            "要求转账": ["转账", "汇款", "付款", "扫码", "押金"],
            "索要验证码": ["验证码", "密码", "验证码", "安全码"],
            "威胁恐吓": ["起诉", "坐牢", "逮捕", "冻结", "黑名单"],
        }
        
        text_lower = text.lower()
        for pattern_name, keywords in common_patterns.items():
            for kw in keywords:
                if kw in text_lower:
                    patterns.append(pattern_name)
                    break
        
        return list(set(patterns))
    
    async def submit_report(
        self,
        user_id: str,
        scam_type: str,
        title: str,
        content: str,
        scammer_contact: Optional[str] = None,
        scammer_account: Optional[str] = None,
        platform: Optional[str] = None,
        amount: Optional[float] = None,
        description: Optional[str] = None,
        evidence_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        提交举报
        
        Args:
            user_id: 用户ID
            scam_type: 诈骗类型
            title: 举报标题
            content: 举报内容（骗子的话术）
            ...
            
        Returns:
            提交结果
        """
        # 提取关键词和模式
        full_text = f"{title} {content} {description or ''}"
        extracted_keywords = self._extract_keywords(full_text)
        extracted_patterns = self._extract_patterns(full_text, scam_type)
        
        # 创建举报记录
        report_id = self._generate_report_id()
        report = ScamReport(
            report_id=report_id,
            user_id=user_id,
            scam_type=self.SCAM_TYPES.get(scam_type, scam_type),
            title=title,
            content=content,
            scammer_contact=scammer_contact,
            scammer_account=scammer_account,
            platform=platform,
            amount=amount,
            description=description,
            evidence_urls=evidence_urls or [],
            status=ReportStatus.PENDING.value,
            source=ReportSource.USER_SUBMISSION.value,
            extracted_keywords=extracted_keywords,
            extracted_patterns=extracted_patterns,
            learned=False,
            created_at=time.time(),
            updated_at=time.time()
        )
        
        self.reports.append(report)
        
        # 保存到数据库
        await self._save_report_to_db(report)
        
        # 举报默认状态为待审核，等待管理员审核后才会接入自进化模块
        # 这确保了举报内容的质量和可靠性
        
        return {
            "success": True,
            "report_id": report.report_id,
            "message": "举报已提交成功！待管理员审核后，举报内容将用于改进AI识别能力。",
            "extracted_info": {
                "keywords": extracted_keywords,
                "patterns": extracted_patterns
            },
            "status": "pending",
            "status_name": "待审核"
        }
    
    async def _save_report_to_db(self, report: ScamReport):
        """保存举报到数据库"""
        try:
            await self.db.insert("scam_reports", {
                "id": report.report_id,
                "report_id": report.report_id,
                "user_id": report.user_id,
                "scam_type": report.scam_type,
                "title": report.title,
                "content": report.content,
                "scammer_contact": report.scammer_contact,
                "scammer_account": report.scammer_account,
                "platform": report.platform,
                "amount": report.amount,
                "description": report.description,
                "evidence_urls": json.dumps(report.evidence_urls, ensure_ascii=False),
                "status": report.status,
                "source": report.source,
                "extracted_keywords": json.dumps(report.extracted_keywords, ensure_ascii=False),
                "extracted_patterns": json.dumps(report.extracted_patterns, ensure_ascii=False),
                "learned": 1 if report.learned else 0,
                "created_at": report.created_at,
                "updated_at": report.updated_at
            })
        except Exception as e:
            print(f"保存举报到数据库失败: {e}")
    
    async def _update_report_in_db(self, report_id: str, updates: Dict):
        """更新数据库中的举报"""
        try:
            await self.db.update("scam_reports", report_id, {"report_id": report_id, **updates})
        except Exception as e:
            print(f"更新举报失败: {e}")
    
    async def get_user_reports(self, user_id: str) -> List[Dict]:
        """获取用户的举报记录"""
        user_reports = [r for r in self.reports if r.user_id == user_id]
        return [self._report_to_dict(r) for r in sorted(user_reports, key=lambda x: x.created_at, reverse=True)]
    
    async def get_report_detail(self, report_id: str, user_id: str) -> Optional[Dict]:
        """获取举报详情"""
        for report in self.reports:
            if report.report_id == report_id and report.user_id == user_id:
                return self._report_to_dict(report)
        return None
    
    async def get_reports_for_evolution(self, limit: int = 10) -> List[Dict]:
        """获取未学习的举报，用于自进化"""
        unlearned = [r for r in self.reports if not r.learned and r.status == ReportStatus.VERIFIED.value]
        return [self._report_to_dict(r) for r in unlearned[:limit]]
    
    async def mark_as_learned(self, report_ids: List[str]):
        """标记为已学习"""
        for report in self.reports:
            if report.report_id in report_ids:
                report.learned = True
                report.updated_at = time.time()
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取举报统计"""
        total = len(self.reports)
        by_status = {}
        by_type = {}
        
        for report in self.reports:
            by_status[report.status] = by_status.get(report.status, 0) + 1
            by_type[report.scam_type] = by_type.get(report.scam_type, 0) + 1
        
        return {
            "total_reports": total,
            "pending_count": by_status.get("pending", 0),
            "verified_count": by_status.get("verified", 0),
            "learned_count": len([r for r in self.reports if r.learned]),
            "by_type": by_type,
            "recent_keywords": self._get_top_keywords(10)
        }
    
    def _get_top_keywords(self, limit: int = 10) -> List[str]:
        """获取高频关键词"""
        keyword_count = {}
        for report in self.reports:
            for kw in report.extracted_keywords or []:
                keyword_count[kw] = keyword_count.get(kw, 0) + 1
        return sorted(keyword_count.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    def _report_to_dict(self, report: ScamReport) -> Dict:
        """转换举报为字典"""
        return {
            "report_id": report.report_id,
            "user_id": report.user_id,
            "scam_type": report.scam_type,
            "scam_type_name": self._get_type_name(report.scam_type),
            "title": report.title,
            "content": report.content,
            "scammer_contact": report.scammer_contact,
            "scammer_account": report.scammer_account,
            "platform": report.platform,
            "amount": report.amount,
            "description": report.description,
            "evidence_urls": report.evidence_urls,
            "status": report.status,
            "status_name": self._get_status_name(report.status),
            "source": report.source,
            "extracted_keywords": report.extracted_keywords,
            "extracted_patterns": report.extracted_patterns,
            "learned": report.learned,
            "created_at": report.created_at,
            "updated_at": report.updated_at
        }
    
    def _get_type_name(self, scam_type: str) -> str:
        """获取诈骗类型中文名"""
        for name, code in self.SCAM_TYPES.items():
            if code == scam_type:
                return name
        return scam_type
    
    def _get_status_name(self, status: str) -> str:
        """获取状态中文名"""
        names = {
            "pending": "待处理",
            "reviewed": "已审核",
            "verified": "已确认",
            "rejected": "已驳回",
            "forwarded": "已转交警方"
        }
        return names.get(status, status)


# 全局实例
report_service = ReportService()
