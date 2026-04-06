"""创建管理员用户脚本"""
import time
import secrets
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.data.database import get_database


async def create_admin():
    db = get_database()
    
    # 生成用户ID
    user_id = 'admin_' + secrets.token_hex(8)
    now = time.time()
    
    # 管理员数据
    admin_data = {
        'id': user_id,
        'username': 'root',
        'password_hash': 'e8bbcd072eb9d2d339994edd0c7cabaf$392e260bf4717eec20ca32104ebd8dbb7551d2b288404ed0363b0e5148c3c170',
        'role': 'admin',
        'is_active': 1,
        'created_at': now,
        'updated_at': now,
        'last_login': None
    }
    
    # 检查是否已存在
    users = await db.query('users_auth', filters={'username': 'root'})
    if users:
        u = users[0]
        user_id = u['id']  # 使用现有用户ID
        # 确保role是admin
        if u.get('role') != 'admin':
            await db.update('users_auth', u['id'], {'role': 'admin'})
            print('已更新现有用户为管理员')
        else:
            print('用户已是管理员')
        print(f'管理员信息:')
        print(f'  用户名: {u["username"]}')
        print(f'  角色: {u.get("role", "user")}')
        print(f'  ID: {u["id"]}')
        
        # 确保用户画像存在
        profiles = await db.query('user_profiles', filters={'user_id': user_id})
        if not profiles:
            profile_data = {
                'user_id': user_id,
                'nickname': 'root',
                'total_consultations': 0,
                'reported_scams': 0,
                'family_protected': 0,
                'risk_count': 0,
                'risk_awareness': 50,
                'interested_scam_types': '[]',
                'learned_topics': '[]',
                'quiz_scores': '{}',
                'updated_at': now
            }
            await db.insert('user_profiles', profile_data)
            print('已创建用户画像')
    else:
        # 插入新用户
        try:
            result = await db.insert('users_auth', admin_data)
            print(f'插入结果: {result}')
            print('管理员创建成功!')
            print(f'  用户名: root')
            print(f'  密码: 1q2w3e4r5t')
            print(f'  角色: admin')
            
            # 创建用户画像
            profile_data = {
                'user_id': user_id,
                'nickname': 'root',
                'total_consultations': 0,
                'reported_scams': 0,
                'family_protected': 0,
                'risk_count': 0,
                'risk_awareness': 50,
                'interested_scam_types': '[]',
                'learned_topics': '[]',
                'quiz_scores': '{}',
                'updated_at': now
            }
            await db.insert('user_profiles', profile_data)
            print('已创建用户画像')
        except Exception as e:
            print(f'创建失败: {e}')


if __name__ == '__main__':
    import asyncio
    asyncio.run(create_admin())
