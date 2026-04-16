"""
SmartGuard - 多模态反诈智能助手
主入口文件

使用方法:
    python main.py
    或
    python main.py --knowledge-base D:\agent\knowledge_base
    或
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.agent import AntiFraudAgent, AgentInput
from src.modules.input_handler import TextInputHandler
from src.data.test_cases import get_test_dataset


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="SmartGuard 反诈智能助手")
    parser.add_argument(
        "--knowledge-base",
        type=str,
        default="D:\\agent\\knowledge_base",
        help="知识库文件夹路径"
    )
    parser.add_argument(
        "--embedding-type",
        type=str,
        choices=["local", "openai"],
        default="local",
        help="嵌入模型类型"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="运行测试模式"
    )
    return parser.parse_args()


async def interactive_mode(agent: AntiFraudAgent):
    """交互模式"""
    print("=" * 60)
    print("🛡️  SmartGuard - 多模态反诈智能助手")
    print("=" * 60)
    print("\n欢迎使用SmartGuard智能反诈助手！")
    print("输入内容进行分析，输入 'quit' 或 'exit' 退出。\n")
    
    while True:
        try:
            user_input = input("\n👤 您: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！祝您生活愉快！")
                break
            
            if not user_input:
                continue
            
            # 创建输入
            input_data = AgentInput(text=user_input, modality="text")
            
            # 处理
            print("\n🤖 分析中...")
            result = await agent.process(input_data)
            
            # 输出结果
            print("\n" + "=" * 60)
            print(f"📊 风险等级: {result.risk_assessment.get('risk_level', 0)}")
            print(f"🔍 风险类型: {result.risk_assessment.get('risk_type', 'normal')}")
            print(f"🎯 置信度: {result.risk_assessment.get('confidence', 0):.2f}")
            print("-" * 60)
            print("📝 分析结果:")
            print(result.response)
            print("=" * 60)
            
            if result.guardian_notified:
                print("\n📞 已通知监护人")
        
        except KeyboardInterrupt:
            print("\n\n👋 已退出")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")


async def test_mode():
    """测试模式"""
    print("=" * 60)
    print("🧪 SmartGuard - 测试模式")
    print("=" * 60)
    
    dataset = get_test_dataset()
    cases = dataset.get_all_cases()
    
    print(f"\n📊 测试集统计:")
    stats = dataset.get_statistics()
    print(f"   总案例数: {stats['total_cases']}")
    print(f"   黑白比例: {stats['black_white_ratio']}")
    print(f"   模态分布: {stats['by_modality']}")
    
    print(f"\n🚀 开始测试...")
    
    agent = AntiFraudAgent(user_id="test_user")
    
    results = {
        "total": len(cases),
        "passed": 0,
        "failed": 0,
        "details": []
    }
    
    for case in cases:
        try:
            input_data = AgentInput(text=case.content, modality=case.modality)
            result = await agent.process(input_data)
            
            # 判断
            predicted_label = "scam" if result.risk_assessment.get("risk_level", 0) >= 2 else "normal"
            correct = predicted_label == case.label
            
            if correct:
                results["passed"] += 1
                status = "✅"
            else:
                results["failed"] += 1
                status = "❌"
            
            print(f"{status} [{case.modality}] {case.case_id}: "
                  f"期望={case.label}, 预测={predicted_label}, "
                  f"风险等级={result.risk_assessment.get('risk_level', 0)}")
            
            results["details"].append({
                "case_id": case.case_id,
                "expected": case.label,
                "predicted": predicted_label,
                "correct": correct
            })
        
        except Exception as e:
            results["failed"] += 1
            print(f"❌ [{case.modality}] {case.case_id}: 错误 - {str(e)}")
    
    # 输出总结
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"总案例数: {results['total']}")
    print(f"通过数: {results['passed']}")
    print(f"失败数: {results['failed']}")
    print(f"准确率: {results['passed'] / results['total'] * 100:.2f}%")
    
    return results


async def demo_mode():
    """演示模式"""
    print("=" * 60)
    print("🎬 SmartGuard - 演示模式")
    print("=" * 60)
    
    agent = AntiFraudAgent(user_id="demo_user")
    
    demo_cases = [
        {
            "name": "冒充公检法诈骗",
            "content": "您好，我是公安局民警，您的身份证被人盗用，涉嫌一起洗钱案件，现在需要您配合调查，请把资金转入安全账户。"
        },
        {
            "name": "投资理财诈骗",
            "content": "我们有一款高收益保本理财产品，年化收益率15%，现在加入还能获得新手礼包，名额有限，先到先得！"
        },
        {
            "name": "正常对话",
            "content": "妈，今天我不回家吃饭了，公司加班。你和爸注意身体。"
        },
        {
            "name": "兼职刷单诈骗",
            "content": "好消息！足不出户，日赚300-500元！只需手机点赞、收藏、加关注，一单一结，感兴趣请加群。"
        },
        {
            "name": "杀猪盘诈骗",
            "content": "亲爱的，我发现了一个赚钱的好机会，跟着导师下注，保证稳赚不赔，我已经赚了好几万了，你要不要一起？"
        }
    ]
    
    for i, demo in enumerate(demo_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"📌 演示案例 {i}: {demo['name']}")
        print(f"{'=' * 60}")
        print(f"输入内容: {demo['content'][:50]}...")
        
        input_data = AgentInput(text=demo["content"], modality="text")
        result = await agent.process(input_data)
        
        risk_level = result.risk_assessment.get("risk_level", 0)
        risk_type = result.risk_assessment.get("risk_type", "normal")
        
        risk_names = {0: "安全", 1: "关注", 2: "警告", 3: "危险", 4: "紧急"}
        
        print(f"\n📊 风险等级: {risk_level} ({risk_names.get(risk_level, '未知')})")
        print(f"🔍 风险类型: {risk_type}")
        print(f"🎯 置信度: {result.risk_assessment.get('confidence', 0):.2f}")
        print(f"\n📝 响应:\n{result.response[:200]}...")
        
        await asyncio.sleep(1)
    
    print("\n" + "=" * 60)
    print("🎬 演示完成！")
    print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SmartGuard - 多模态反诈智能助手"
    )
    
    parser.add_argument(
        "mode",
        nargs="?",
        default="interactive",
        choices=["interactive", "test", "demo", "api"],
        help="运行模式: interactive(交互), test(测试), demo(演示), api(API服务)"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="API服务主机地址"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API服务端口"
    )
    
    args = parser.parse_args()
    
    if args.mode == "interactive":
        asyncio.run(interactive_mode())
    
    elif args.mode == "test":
        asyncio.run(test_mode())
    
    elif args.mode == "demo":
        asyncio.run(demo_mode())
    
    elif args.mode == "api":
        import uvicorn
        print(f"🚀 启动API服务: http://{args.host}:{args.port}")
        uvicorn.run(
            "src.api.main:app",
            host=args.host,
            port=args.port,
            reload=True
        )


if __name__ == "__main__":
    main()