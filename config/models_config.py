# 模型服务配置
# 在此处配置所有模型的 API Key，方便统一管理

MODELS_CONFIG = [
    {
        'name': 'DeepSeek V3',
        'code': 'deepseek-v3',
        'api_url': 'https://aigc-api.aitoolcore.com/api/v1/chat/completions',
        'api_key': 'sk-aigc-c0725a1b8a1b205154867945a3c667ce9d232fa7',
        'status': 1,
        'is_system_default': 1,
    },
    {
        'name': 'DeepSeek-R1-Distill-Qwen-7B',
        'code': 'deepseek-r1-distill-qwen-7b',
        'api_url': 'https://aigc-api.aitoolcore.com/api/v1/chat/completions',
        'api_key': 'sk-aigc-c0725a1b8a1b205154867945a3c667ce9d232fa7',
        'status': 1,
        'is_system_default': 0,
    },
]

def get_model_config(code):
    """根据模型编码获取配置"""
    for m in MODELS_CONFIG:
        if m['code'] == code:
            return m
    return None

def get_enabled_models():
    """获取所有启用的模型配置"""
    return [m for m in MODELS_CONFIG if m['status'] == 1]

def get_default_model_config():
    """获取系统默认模型配置"""
    for m in MODELS_CONFIG:
        if m['is_system_default'] == 1 and m['status'] == 1:
            return m
    return None
