"""
提交测试举报用例，验证自进化流程：
  1. 用户提交举报（status=PENDING）
  2. 管理员审核通过（status=VERIFIED）
  3. 触发自进化，将关键词和模式写入知识库
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.report_submit_service import report_service as report_svc
from src.services.evolution_service import get_evolution_service as get_evol


async def main():
    evol_svc  = get_evol()

    # 案例 1: 杀猪盘
    await report_svc.submit_report(
        user_id    = "test_user_001",
        scam_type  = "杀猪盘",
        title      = "网恋对象带我投资平台，亏了20万",
        content    = (
            "在某社交APP认识一个女生，聊了两个月，她说她在做加密货币投资，"
            "让我跟着她一起买USDT。我下载了一个叫CryptoWin的平台，"
            "先充了5000元试水，收益提现了800元。然后客服说充30万才能提现，"
            "我又转了20万进去，结果平台说银行卡号填错需要交10万保证金。"
            "这时我才意识到可能是骗局，对方微信号是 love520888，"
            "平台客服一直催我转账。转账用的卡号：6228 **** 1234"
        ),
        scammer_contact = "love520888",
        amount     = 210000.0,
    )
    print("[+] 举报1 已提交: 杀猪盘 / 网恋带你投资")

    # 案例 2: 刷单返利
    await report_svc.submit_report(
        user_id    = "test_user_002",
        scam_type  = "刷单返利",
        title      = "抖音点赞刷单，先赚后亏",
        content    = (
            "收到一条短信：【抖音官方】您被随机抽中为优质用户，"
            "加客服微信号dyvip888做任务，每天可赚300-800元。"
            "加了微信后，对方发来一个链接，让我下载「乐购任务」APP，"
            "说在里面做刷单任务。做前两单都返了10元和30元，"
            "第三单变成连单，要连续做三笔，金额分别是500、2000、8800元，"
            "做完才能提现。我转了11300元后，客服说我操作超时需要重新打款。"
            "收款账户：6217 **** 9876  户名：张XX"
        ),
        scammer_contact = "dyvip888",
        amount     = 11300.0,
    )
    print("[+] 举报2 已提交: 刷单返利 / 抖音点赞")

    # 案例 3: 冒充公检法
    await report_svc.submit_report(
        user_id    = "test_user_003",
        scam_type  = "冒充公检法",
        title      = "接到上海公安局电话，说我洗钱",
        content    = (
            "接到一个自称上海公安局的电话（+86 21 110），"
            "说我的身份证被人用来开通银行卡洗钱，涉及200万资金，"
            "已经被通缉。然后帮我转接了「检察官」，"
            "检察官让我把钱转到「安全账户」进行核查。"
            "按照对方指示，我将农业银行卡（6228 **** 5566）里的"
            "15万元转到了对方提供的「核查账户」。"
            "对方一直强调这是机密案件，不能告诉任何人，"
            "也不要去派出所核实。转账时用的是手机银行，"
            "收款人信息写着「上海市人民检察院」。"
            "第二天再打电话已经打不通了。"
        ),
        scammer_contact = "+86 21 110",
        amount     = 150000.0,
    )
    print("[+] 举报3 已提交: 冒充公检法 / 安全账户")

    # 打印当前举报列表
    print(f"\n当前举报总数: {len(report_svc.reports)}")
    for r in report_svc.reports:
        print(f"  [{r.report_id}] {r.scam_type} | {r.title} | status={r.status}")

    # 模拟管理员审核全部通过
    print("\n>>> 模拟管理员审核通过...")
    evol_svc.learned_keywords.clear()
    evol_svc.learned_patterns.clear()

    for r in report_svc.reports:
        if r.status == "pending":
            r.status = "verified"
            r.learned = False
            await evol_svc.record_case(
                user_id    = r.user_id,
                content    = r.content,
                risk_level = 4,
                risk_type  = r.scam_type,
                analysis   = "用户提交的举报案例，经管理员审核通过后纳入自进化学习",
                response   = f"已学习举报案例: {r.title}",
            )
    print("[+] 所有举报已标记为 VERIFIED，并触发学习")

    # 查看学到的关键词/模式
    stats = evol_svc.get_evolution_stats()
    kw_count = stats.get("knowledge_count", {})
    print(f"\n学习统计:")
    print(f"  待学习案例: {stats.get('pending_cases', 0)}")
    print(f"  已学关键词数: {kw_count.get('keywords', 0)}")
    print(f"  已学模式数: {kw_count.get('patterns', 0)}")
    print("\n关键词库:")
    for kw_type, kw_list in evol_svc.learned_keywords.items():
        print(f"  [{kw_type}] ({len(kw_list)} 个)")
        for k in kw_list[:5]:
            print(f"    - {k}")
    print("\n模式库:")
    for pt_type, pt_list in evol_svc.learned_patterns.items():
        print(f"  [{pt_type}] ({len(pt_list)} 个)")
        for p in pt_list[:3]:
            print(f"    - {p}")

    print("\n[OK] 测试用例已全部处理完毕，请在管理后台「自进化知识库」页面查看效果。")


if __name__ == "__main__":
    asyncio.run(main())
