# Unitree G1-23DOF RL Policy 技术对接文档

## 1. 环境基本信息

### 任务标识
- **任务名称**: `Unitree-G1-23Dof-Flat` (平地行走)
- **其他变体**: 
  - `Unitree-G1-23Dof-Rough` (粗糙地形)
  - `Unitree-G1-23Dof-Tracking` (轨迹跟踪)

### 控制频率
- **物理仿真步长**: 0.005 秒 (200 Hz)
- **控制步长**: 0.02 秒 (50 Hz)
- **Decimation**: 4 (每4个物理步执行一次策略)

---

## 2. 机器人控制接口

### 2.1 关节信息
- **关节数量**: 23 个可控关节
- **关节列表**: (按索引顺序)
```
[0-5]   左腿: left_hip_pitch, left_hip_roll, left_hip_yaw, left_knee, left_ankle_pitch, left_ankle_roll
[6-11]  右腿: right_hip_pitch, right_hip_roll, right_hip_yaw, right_knee, right_ankle_pitch, right_ankle_roll
[12-14] 腰部: waist_yaw, waist_roll, waist_pitch
[15-18] 左臂: left_shoulder_pitch, left_shoulder_roll, left_shoulder_yaw, left_elbow
[19-22] 右臂: right_shoulder_pitch, right_shoulder_roll, right_shoulder_yaw, right_elbow
```

### 2.2 动作空间
- **维度**: 23 (对应23个关节)
- **类型**: 关节位置偏移量 (Joint Position Action)
- **输入范围**: `[-1, 1]` (归一化值)
- **缩放**: 动作会被缩放系数转换为实际关节偏移量
  - 具体缩放系数见 `G1_23DOF_ACTION_SCALE` (在 `src/assets/robots/__init__.py`)
- **控制模式**: 相对于默认姿态的位置偏移
- **公式**: `target_position = default_position + action * scale`

---

## 3. 速度命令接口 (Twist Command)

### 3.1 命令维度
**3维向量**: `[lin_vel_x, lin_vel_y, ang_vel_z]`

### 3.2 命令详细说明
```python
命令[0] = lin_vel_x  # 前进速度 (m/s)
  - 正值: 前进
  - 负值: 后退
  - 训练范围: [-1.0, 2.0] m/s
  
命令[1] = lin_vel_y  # 横向速度 (m/s) 
  - 正值: 向左移动
  - 负值: 向右移动
  - 训练范围: [-1.0, 1.0] m/s
  
命令[2] = ang_vel_z  # 旋转速度 (rad/s)
  - 正值: 逆时针旋转
  - 负值: 顺时针旋转
  - 训练范围: [-1.0, 1.0] rad/s
```

### 3.3 测试时固定速度命令的方法
```python
# 方法1: 使用提供的测试脚本
python scripts/play_straight.py \
  --checkpoint-file=<path_to_checkpoint> \
  --linear-velocity-x 0.8 \
  --linear-velocity-y 0.0 \
  --angular-velocity-z 0.0

# 方法2: 修改配置中的命令范围
twist_cmd.ranges.lin_vel_x = (0.8, 0.8)  # 固定为0.8 m/s
twist_cmd.ranges.lin_vel_y = (0.0, 0.0)  # 固定为0
twist_cmd.ranges.ang_vel_z = (0.0, 0.0)  # 固定为0
```

---

## 4. 观测空间 (Actor Observation)

### 4.1 观测维度
**总维度**: 80

### 4.2 观测组成 (按索引顺序)
```python
观测向量 = [
  base_ang_vel,         # [0:3]   机身角速度 (IMU) (rad/s)
  projected_gravity,    # [3:6]   投影重力向量 (归一化)
  command,              # [6:9]   速度命令 [lin_vel_x, lin_vel_y, ang_vel_z]
  phase,                # [9:11]  步态相位 [sin(phase), cos(phase)]
  joint_pos,            # [11:34] 23个关节位置 (相对于默认姿态) (rad)
  joint_vel,            # [34:57] 23个关节速度 (rad/s)
  actions,              # [57:80] 上一时刻的动作 (23维)
]
```

### 4.3 观测说明
- **base_ang_vel**: 机身在body frame下的角速度，来自IMU传感器
- **projected_gravity**: 重力在机身坐标系下的投影，用于感知姿态
- **command**: 当前的速度命令目标
- **phase**: 步态周期相位，周期为0.6秒
- **joint_pos**: 关节位置偏移量（相对默认站立姿态）
- **joint_vel**: 关节速度
- **actions**: 历史动作，用于增强策略的时序记忆

### 4.4 观测噪声
- **训练时**: 各观测项添加了噪声以提高鲁棒性
- **测试时**: 可以通过 `env_cfg.observations["actor"].enable_corruption = False` 禁用噪声

---

## 5. RL Policy 加载和使用

### 5.1 加载策略的完整代码
```python
import torch
from pathlib import Path
from dataclasses import asdict
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls

# 1. 加载任务配置
task_id = 'Unitree-G1-23Dof-Flat'
env_cfg = load_env_cfg(task_id, play=True)
agent_cfg = load_rl_cfg(task_id)

# 2. 设置环境参数
env_cfg.scene.num_envs = 1
device = "cuda:0" if torch.cuda.is_available() else "cpu"

# 3. 创建环境
env = ManagerBasedRlEnv(cfg=env_cfg, device=device)
env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

# 4. 加载策略
checkpoint_path = Path("path/to/model_10000.pt")
runner_cls = load_runner_cls(task_id)
if runner_cls is None:
    runner_cls = MjlabOnPolicyRunner

runner = runner_cls(env, asdict(agent_cfg), device=device)
runner.load(
    str(checkpoint_path),
    load_cfg={"actor": True},
    strict=True,
    map_location=device
)
policy = runner.get_inference_policy(device=device)

# 5. 运行策略
obs, _ = env.reset()
for step in range(1000):
    with torch.inference_mode():
        actions = policy(obs)  # 输入: (1, 80), 输出: (1, 23)
    obs, rewards, dones, truncated, info = env.step(actions)
```

### 5.2 策略输入输出规格
```python
# 输入
observation: torch.Tensor
  - Shape: (num_envs, 80)
  - Dtype: torch.float32
  - Device: 与策略相同 (cuda:0 或 cpu)
  - 范围: 各项观测已归一化或在合理物理范围内

# 输出
action: torch.Tensor
  - Shape: (num_envs, 23)
  - Dtype: torch.float32
  - Device: 与策略相同
  - 范围: 理论上 [-1, 1]，但策略可能输出略超出范围的值
  - RslRlVecEnvWrapper 会根据 clip_actions 配置进行裁剪
```

### 5.3 Checkpoint 文件格式
```python
checkpoint = torch.load("model_10000.pt")
# 包含的键:
# - 'model_state_dict': 策略网络参数
# - 'optimizer_state_dict': 优化器状态 (可选)
# - 'iter': 训练迭代次数 (可选)
```

---

## 6. 与环境的集成接口

### 6.1 环境重置
```python
obs, info = env.reset()
# obs: (num_envs, 80) 初始观测
# info: dict, 包含额外信息
```

### 6.2 环境步进
```python
obs, rewards, dones, truncated, info = env.step(actions)
# obs: (num_envs, 80) 新观测
# rewards: (num_envs,) 奖励值
# dones: (num_envs,) 是否终止 (摔倒等)
# truncated: (num_envs,) 是否超时
# info: dict, 包含额外信息
```

### 6.3 获取机器人状态
```python
robot = env.unwrapped.scene['robot']

# 基座状态
pos_w = robot.data.root_link_pos_w        # (num_envs, 3) 世界坐标系位置
quat_w = robot.data.root_link_quat_w      # (num_envs, 4) 世界坐标系四元数
lin_vel_b = robot.data.root_link_lin_vel_b  # (num_envs, 3) 本体坐标系线速度
ang_vel_b = robot.data.root_link_ang_vel_b  # (num_envs, 3) 本体坐标系角速度

# 关节状态
joint_pos = robot.data.joint_pos          # (num_envs, 23) 关节位置
joint_vel = robot.data.joint_vel          # (num_envs, 23) 关节速度
```

### 6.4 设置速度命令
```python
# 获取命令管理器
cmd_manager = env.unwrapped.command_manager

# 获取当前命令
current_cmd = cmd_manager.get_command("twist")  # (num_envs, 3)

# 直接设置命令 (如果需要手动控制)
cmd_term = cmd_manager._terms["twist"]
cmd_term.vel_command_b[env_id] = torch.tensor([lin_vel_x, lin_vel_y, ang_vel_z])
```

---

## 7. 关键配置参数

### 7.1 奖励权重 (影响策略行为)
```python
track_linear_velocity: 1.0      # 线速度跟踪
track_angular_velocity: 1.0     # 角速度跟踪
body_orientation_l2: -1.0       # 保持身体姿态
pose: 1.0                       # 保持自然姿态
action_rate_l2: -0.05          # 动作平滑度
foot_gait: 0.5                  # 步态奖励
...
```

### 7.2 训练时的域随机化 (Domain Randomization)
```python
- encoder_bias: ±0.015 rad      # 关节编码器偏差
- base_com: ±0.05 m             # 质心偏移
- foot_friction: 0.3-1.6        # 脚部摩擦系数
- observation_noise: 各有不同   # 观测噪声
```

---

## 8. 常见问题

### Q1: 策略输出的动作超出 [-1, 1] 范围怎么办？
A: `RslRlVecEnvWrapper` 会根据配置自动裁剪。如果需要手动裁剪：
```python
actions = torch.clamp(actions, -1.0, 1.0)
```

### Q2: 如何禁用域随机化进行测试？
A:
```python
env_cfg.events.pop("encoder_bias", None)
env_cfg.events.pop("base_com", None)
env_cfg.events.pop("foot_friction", None)
env_cfg.observations["actor"].enable_corruption = False
```

### Q3: 如何可视化机器人运动？
A: 使用 Viser 可视化器：
```python
# 在命令行
python scripts/play.py Unitree-G1-23Dof-Flat \
  --checkpoint_file=<path> \
  --num-envs 1 \
  --viewer viser

# 浏览器访问 http://localhost:8080
```

### Q4: 观测中的关节位置是绝对值还是相对值？
A: **相对值**，相对于默认站立姿态的偏移量。
```python
observed_joint_pos = actual_joint_pos - default_joint_pos
```

### Q5: 策略的延迟是多少？
A: 
- 控制频率: 50 Hz (每 0.02 秒)
- 策略推理延迟: < 1ms (GPU) 或 < 5ms (CPU)
- 总延迟: ~20-25ms

---

## 9. 联系信息和参考

### 代码库结构
```
unitree_rl_mjlab/
├── scripts/
│   ├── play.py              # 标准测试脚本
│   ├── play_straight.py     # 固定速度命令测试脚本
│   └── train.py             # 训练脚本
├── src/
│   ├── assets/robots/       # 机器人模型和配置
│   └── tasks/
│       └── velocity/        # 速度任务配置
│           ├── config/
│           │   └── g1_23dof/
│           │       └── env_cfgs.py  # G1-23DOF 环境配置
│           └── mdp/
│               └── velocity_command.py  # 速度命令实现
└── README.md
```

### 关键配置文件
- 环境配置: `src/tasks/velocity/config/g1_23dof/env_cfgs.py`
- 训练配置: `src/tasks/velocity/config/g1_23dof/rl_cfg.py`
- 速度命令实现: `src/tasks/velocity/mdp/velocity_command.py`

---

## 10. 快速集成示例

```python
#!/usr/bin/env python3
"""最小化的策略集成示例"""

import torch
from pathlib import Path
from dataclasses import asdict
import mjlab.tasks
import src.tasks
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg

def load_policy(checkpoint_path: str, device: str = "cuda:0"):
    """加载训练好的策略"""
    task_id = 'Unitree-G1-23Dof-Flat'
    env_cfg = load_env_cfg(task_id, play=True)
    agent_cfg = load_rl_cfg(task_id)
    
    env_cfg.scene.num_envs = 1
    env = ManagerBasedRlEnv(cfg=env_cfg, device=device)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    
    runner = MjlabOnPolicyRunner(env, asdict(agent_cfg), device=device)
    runner.load(checkpoint_path, load_cfg={"actor": True}, map_location=device)
    policy = runner.get_inference_policy(device=device)
    
    return env, policy

def run_policy(env, policy, target_vel_x=0.8, num_steps=1000):
    """运行策略"""
    # 设置固定速度命令
    twist_cmd = env.unwrapped.command_manager._terms["twist"]
    twist_cmd.vel_command_b[:] = torch.tensor([target_vel_x, 0.0, 0.0])
    
    obs, _ = env.reset()
    
    for step in range(num_steps):
        with torch.inference_mode():
            actions = policy(obs)  # (1, 80) -> (1, 23)
        obs, _, _, _, _ = env.step(actions)
    
    env.close()

if __name__ == "__main__":
    checkpoint = str(Path.home() / "unitree_RL/model_10000.pt")
    env, policy = load_policy(checkpoint)
    run_policy(env, policy, target_vel_x=0.8, num_steps=1000)
```

---

**文档版本**: v1.0  
**最后更新**: 2026-06-18  
**适用模型**: model_10000.pt (10000 iterations)
