# AI_THE_SPIRE 项目依赖

# ==================== 核心依赖 ====================

# 数值计算
numpy>=1.24.0,<2.0.0
scipy>=1.10.0,<2.0.0

# 机器学习
scikit-learn>=1.3.0
torch>=2.0.0

# 强化学习
stable-baselines3>=2.0.0
gymnasium>=0.29.0

# 配置管理
pyyaml>=6.0

# ==================== 可选依赖 ====================

# 数据可视化
matplotlib>=3.7.0
tensorboard>=2.12.0

# 进度条
tqdm>=4.65.0

# ==================== 开发依赖 ====================

# 测试
pytest>=7.0.0
pytest-cov>=4.0.0

# 代码质量
black>=23.0.0
flake8>=6.0.0
mypy>=1.0.0

# ==================== 说明 ====================

# 1. 基础安装：
#    pip install -r requirements.txt

# 2. 仅安装核心依赖（最小化安装）：
#    pip install numpy scipy scikit-learn torch stable-baselines3 gymnasium pyyaml

# 3. 仅安装开发依赖：
#    pip install pytest pytest-cov black flake8 mypy

# ==================== 已知问题 ====================

# sklearn 与 numpy 2.0+ 兼容性问题：
#   如果遇到 "AttributeError: _ARRAY_API not found" 错误
#   解决方案：使用 PyTorch 后端替代 sklearn
#
#   示例：
#   python scripts/train.py sl --model-type pytorch
