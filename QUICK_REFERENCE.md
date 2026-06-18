# RL Policy 快速参考卡片

## 核心参数速查

### 输入输出
```
观测维度: 80
动作维度: 23
命令维度: 3 [lin_vel_x, lin_vel_y, ang_vel_z]
控制频率: 50 Hz (0.02s)
```

### 速度命令 (Twist Command)
```python
command = [lin_vel_x, lin_vel_y, ang_vel_z]
         # [前进m/s, 横向m/s, 旋转rad/s]

# 训练范围
lin_vel_x: [-1.0, 2.0] m/s   # 前进
lin_vel_y: [-1.0, 1.0] m/s   # 左右
ang_vel_z: [-1.0, 1.0] rad/s # 旋转

# 测试示例
[0.8, 0.0, 0.0]  # 前进 0.8 m/s
[0.0, 0.5, 0.0]  # 左移 0.5 m/s
[0.0, 0.0, 0.5]  # 逆时针 0.5 rad/s
```

### 观测向量 (80维)
```python
[0:3]    base_ang_vel         # 机身角速度 (IMU)
[3:6]    projected_gravity    # 投影重力
[6:9]    command              # 速度命令
[9:11]   phase                # 步态相位
[11:34]  joint_pos (23)       # 关节位置
[34:57]  joint_vel (23)       # 关节速度
[57:80]  actions (23)         # 上一时刻动作
```

### 动作向量 (23维)
```python
关节顺序:
[0-5]   左腿 (hip_pitch, hip_roll, hip_yaw, knee, ankle_pitch, ankle_roll)
[6-11]  右腿 (同上)
[12-14] 腰部 (waist_yaw, waist_roll, waist_pitch)
[15-18] 左臂 (shoulder_pitch, shoulder_roll, shoulder_yaw, elbow)
[19-22] 右臂 (同上)

动作范围: [-1, 1] (归一化的关节位置偏移)
```

## 最小化代码示例

### 加载策略
```python
import torch
from dataclasses import asdict
import mjlab.tasks, src.tasks
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg

# 加载
task_id = 'Unitree-G1-23Dof-Flat'
env_cfg = load_env_cfg(task_id, play=True)
agent_cfg = load_rl_cfg(task_id)
env_cfg.scene.num_envs = 1

device = "cuda:0"
env = ManagerBasedRlEnv(cfg=env_cfg, device=device)
env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

runner = MjlabOnPolicyRunner(env, asdict(agent_cfg), device=device)
runner.load("model_10000.pt", load_cfg={"actor": True}, map_location=device)
policy = runner.get_inference_policy(device=device)
```

### 运行推理
```python
obs, _ = env.reset()  # obs: (1, 80)

for step in range(1000):
    with torch.inference_mode():
        actions = policy(obs)  # obs: (1,80) -> actions: (1,23)
    obs, rewards, dones, truncated, info = env.step(actions)
```

### 设置固定速度命令
```python
# 方法1: 修改配置
from mjlab.tasks.velocity.mdp import UniformVelocityCommandCfg
twist_cmd = env_cfg.commands['twist']
twist_cmd.ranges.lin_vel_x = (0.8, 0.8)
twist_cmd.ranges.lin_vel_y = (0.0, 0.0)
twist_cmd.ranges.ang_vel_z = (0.0, 0.0)

# 方法2: 运行时修改
cmd_term = env.unwrapped.command_manager._terms["twist"]
cmd_term.vel_command_b[:] = torch.tensor([[0.8, 0.0, 0.0]], device=device)
```

### 获取机器人状态
```python
robot = env.unwrapped.scene['robot']

# 基座状态
pos = robot.data.root_link_pos_w[0]      # (3,) 位置
quat = robot.data.root_link_quat_w[0]    # (4,) 四元数
vel_b = robot.data.root_link_lin_vel_b[0] # (3,) 线速度
ang_vel_b = robot.data.root_link_ang_vel_b[0] # (3,) 角速度

# 关节状态
joint_pos = robot.data.joint_pos[0]      # (23,) 关节位置
joint_vel = robot.data.joint_vel[0]      # (23,) 关节速度
```

## 测试命令

### 命令行测试
```bash
# 标准测试（随机速度命令）
python scripts/play.py Unitree-G1-23Dof-Flat \
  --checkpoint_file=$HOME/unitree_RL/model_10000.pt \
  --num-envs 1 \
  --viewer viser

# 固定速度测试（走直线）
python scripts/play_straight.py \
  --checkpoint-file=$HOME/unitree_RL/model_10000.pt \
  --linear-velocity-x 0.8 \
  --linear-velocity-y 0.0 \
  --angular-velocity-z 0.0 \
  --num-envs 1 \
  --viewer viser

# 浏览器访问: http://localhost:8080
```

### 禁用域随机化（纯净测试）
```python
env_cfg.events.pop("encoder_bias", None)
env_cfg.events.pop("base_com", None)
env_cfg.events.pop("foot_friction", None)
env_cfg.observations["actor"].enable_corruption = False
```

## 常见问题

**Q: 观测中的关节位置是绝对值吗？**  
A: 不是，是相对默认姿态的偏移量

**Q: 动作超出 [-1,1] 怎么办？**  
A: RslRlVecEnvWrapper 会自动裁剪

**Q: 策略延迟是多少？**  
A: ~20ms (包括推理 <1ms + 控制周期 20ms)

**Q: 如何切换到CPU运行？**  
A: 设置 `device="cpu"`，推理速度 ~5ms

**Q: 如何可视化速度命令？**  
A: 在 Viser 中看蓝色箭头（命令）vs 青色箭头（实际）

## 关键文件路径

```
unitree_rl_mjlab/
├── scripts/
│   ├── play.py                    # 标准测试
│   └── play_straight.py           # 固定速度测试
├── src/tasks/velocity/
│   ├── config/g1_23dof/
│   │   └── env_cfgs.py           # 环境配置
│   └── mdp/
│       └── velocity_command.py    # 速度命令实现
└── INTEGRATION_GUIDE.md           # 完整对接文档
```

## 依赖环境

```bash
# 必须在 unitree_rl_mjlab conda 环境中运行
conda activate unitree_rl_mjlab

# 验证环境
python -c "import mjlab; import src.tasks; print('OK')"
```

---
**参考完整文档**: [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
