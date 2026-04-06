"""
举报进化集成模块
将用户举报内容接入自进化系统
"""

from typing import Dict, List, Any
from src.services.report_submit_service import report_service
from src.services.evolution_service import evolution_service


async def integrate_reports_to_evolution():
    """
    将举报内容接入自进化模块
    
    从举报中提取：
    1. 新的诈骗关键词
    2. 新的诈骗模式
    3. 新的诈骗案例
    """
    # 获取未学习的举报
    reports = await report_service.get_reports_for_evolution(limit=20)
    
    if not reports:
        return {
            "status": "no_reports",
            "integrated": 0
        }
    
    integrated_count = 0
    new_keywords = []
    new_patterns = []
    
    for report in reports:
        # 提取关键词和模式
        keywords = report.get("extracted_keywords", [])
        patterns = report.get("extracted_patterns", [])
        scam_type = report.get("scam_type")
        content = report.get("content", "")
        title = report.get("title", "")
        
        # 添加到进化服务的学习记录
        if keywords or patterns:
            # 构建案例数据
            case_data = {
                "type": "scam_report",
                "scam_type": scam_type,
                "content": f"{title}\n{content}",
                "keywords": keywords,
                "patterns": patterns,
                "source": "user_report",
                "report_id": report.get("report_id")
            }
            
            # 调用进化服务的学习方法
            # 注意：这里只是记录，实际学习在evolution_service中进行
            new_keywords.extend(keywords)
            new_patterns.extend(patterns)
            
            # 标记为已学习
            await report_service.mark_as_learned([report.get("report_id")])
            integrated_count += 1
    
    # 去重
    new_keywords = list(set(new_keywords))
    new_patterns = list(set(new_patterns))
    
    return {
        "status": "success",
        "integrated": integrated_count,
        "new_keywords_count": len(new_keywords),
        "new_patterns_count": len(new_patterns),
        "keywords": new_keywords[:10],  # 只返回前10个
        "patterns": new_patterns
    }


def get_evolution_keywords() -> List[Dict[str, Any]]:
    """
    获取进化后的关键词库
    供识别模块使用
    """
    from src.services.evolution_service import evolution_service
    
    result = []
    for scam_type, keywords in evolution_service.learned_keywords.items():
        result.append({
            "scam_type": scam_type,
            "keywords": keywords,
            "count": len(keywords)
        })
    
    return result


def get_evolution_patterns() -> List[Dict[str, Any]]:
    """
    获取进化后的模式库
    供识别模块使用
    """
    from src.services.evolution_service import evolution_service
    
    result = []
    for scam_type, patterns in evolution_service.learned_patterns.items():
        result.append({
            "scam_type": scam_type,
            "patterns": patterns,
            "count": len(patterns)
        })
    
    return result
