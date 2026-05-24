from app.models.user import UserRepository

print("=" * 60)
print("测试分页逻辑")
print("=" * 60)

# 测试第 1 页，每页 4 条
print("\n【第 1 页，page_size=4】")
result = UserRepository.get_user_list(page=1, page_size=4)
print(f"总数：{result['total']}")
print(f"返回数据：{len(result['data'])} 条")
for i, row in enumerate(result['data'], 1):
    print(f"  {i}. {row['username']} - {row['role']}")

# 测试第 2 页，每页 4 条
print("\n【第 2 页，page_size=4】")
result = UserRepository.get_user_list(page=2, page_size=4)
print(f"总数：{result['total']}")
print(f"返回数据：{len(result['data'])} 条")
for i, row in enumerate(result['data'], 1):
    print(f"  {i}. {row['username']} - {row['role']}")

# 测试第 1 页，每页 20 条（默认值）
print("\n【第 1 页，page_size=20（默认）】")
result = UserRepository.get_user_list(page=1)
print(f"总数：{result['total']}")
print(f"返回数据：{len(result['data'])} 条")
for i, row in enumerate(result['data'], 1):
    print(f"  {i}. {row['username']} - {row['role']}")

print("\n" + "=" * 60)
