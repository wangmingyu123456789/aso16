"""
app包：mvc 业务代码入口
说明：
- 这个文件的存在表示app/是一个python包(package)
- __init__.py便于导入与IDE识别
"""

import os
import importlib.util

# 从项目根目录的 app.py 加载 make_app 函数
_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "app_root_module",
    os.path.join(_root_dir, "app.py")
)
_app_root = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_app_root)
make_app = _app_root.make_app
