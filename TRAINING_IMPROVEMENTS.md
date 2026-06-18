"""建议的训练配置改进

针对直线行走偏移问题的改进方案
"""

# 1. 收紧速度跟踪奖励的容忍度
# 在 velocity_env_cfg.py 中修改：

rewards = {
    "track_linear_velocity": RewardTermCfg(
        func=mdp.track_linear_velocity,
        weight=1.5,  # 增加权重从 1.0 -> 1.5
        params={"command_name": "twist", "std": 0.35},  # 减小std从 sqrt(0.25)=0.5 -> 0.35
    ),
    "track_angular_velocity": RewardTermCfg(
        func=mdp.track_angular_velocity,
        weight=1.5,  # 增加权重从 1.0 -> 1.5
        params={"command_name": "twist", "std": 0.5},  # 减小std从 sqrt(0.5)=0.707 -> 0.5
    ),
    
    # 2. 添加显式的横向漂移惩罚
    "lateral_drift_penalty": RewardTermCfg(
        func=mdp.lateral_drift,  # 需要实现这个函数
        weight=-0.5,
        params={"command_name": "twist", "threshold": 0.1},
    ),
}

# 3. 确保训练命令分布平衡
# 在 env_cfgs.py 中，确保对称的命令范围：

commands = {
    "twist": UniformVelocityCommandCfg(
        ranges=UniformVelocityCommandCfg.Ranges(
            lin_vel_x=(-1.0, 2.0),  # 保持前进偏向，符合实际使用
            lin_vel_y=(-0.8, 0.8),  # 确保左右对称
            ang_vel_z=(-1.0, 1.0),  # 确保旋转对称
            heading=(-math.pi, math.pi),  # 确保朝向对称
        ),
    )
}

# 4. 增加对称性随机化
# 确保左右脚的随机化是对称的：

events = {
    "foot_friction": EventTermCfg(
        mode="startup",
        func=dr.geom_friction,
        params={
            "shared_random": True,  # 确保左右脚共享相同的摩擦系数
        },
    ),
}

# 5. 从当前checkpoint继续训练
# 使用 resume 功能继续训练，而不是从头开始：
# python scripts/train.py Unitree-G1-23Dof-Flat --resume --checkpoint_file=$HOME/unitree_RL/model_10000.pt

"""
总结：
1. 先用 quick_test.py 量化偏移程度
2. 如果偏移 > 10%，checkpoint 需要改进
3. 小于 5% 的偏移是可接受的
4. 继续训练比从头开始更有效
"""
