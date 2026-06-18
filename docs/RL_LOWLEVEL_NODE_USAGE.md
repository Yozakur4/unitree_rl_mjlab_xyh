# RL Policy LowLevel Node 使用说明

## 功能

ROS 节点，用于：
1. 订阅速度命令 (vx, vy, yaw_rate)
2. 运行 RL Policy 生成关节指令
3. 发布 LowLevelCmd 格式的指令给仿真/真机

## 使用方法

### 1. 直接运行节点

```bash
# 激活环境
conda activate unitree_rl_mjlab

# 运行节点
python scripts/rl_policy_lowlevel_node.py \
  _checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  _device:=cuda:0 \
  _control_rate:=50
```

### 2. 使用 rosrun

```bash
# 确保脚本可执行
chmod +x scripts/rl_policy_lowlevel_node.py

# 运行
rosrun unitree_rl_control rl_policy_lowlevel_node.py
```

### 3. 使用 launch 文件

```bash
roslaunch unitree_rl_control rl_policy_lowlevel.launch \
  checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  device:=cuda:0
```

## 参数配置

### 必需参数

- `checkpoint_path`: RL Policy checkpoint 文件路径
  - 默认: `$HOME/unitree_RL/model_10000.pt`

### 可选参数

- `device`: 计算设备
  - 默认: `cuda:0`
  - 可选: `cpu`, `cuda:1`, 等

- `control_rate`: 控制频率 (Hz)
  - 默认: `50`
  - 推荐: 保持 50Hz

- `Kp`: PD 控制比例增益
  - 默认: `50.0`
  - 需要根据实际机器人调整

- `Kd`: PD 控制微分增益
  - 默认: `1.0`
  - 需要根据实际机器人调整

### ROS 话题配置

- `cmd_vel_topic`: 速度命令输入话题
  - 默认: `/cmd_vel`
  - 消息类型: `geometry_msgs/Twist`

- `imu_topic`: IMU 数据输入话题
  - 默认: `/trunk_imu`
  - 消息类型: `sensor_msgs/Imu`

- `joint_states_topic`: 关节状态输入话题
  - 默认: `/joint_states`
  - 消息类型: `sensor_msgs/JointState`

- `lowcmd_topic`: 低级指令输出话题
  - 默认: `/lowcmd`
  - 消息类型: `unitree_legged_msgs/LowCmd`

## 订阅的话题

### `/cmd_vel` (geometry_msgs/Twist)

速度命令输入：

```yaml
linear:
  x: float  # 前进速度 (m/s), 范围 [-1.0, 2.0]
  y: float  # 横向速度 (m/s), 范围 [-1.0, 1.0]
  z: float  # 未使用
angular:
  x: float  # 未使用
  y: float  # 未使用
  z: float  # 旋转速度 (rad/s), 范围 [-1.0, 1.0]
```

### `/trunk_imu` (sensor_msgs/Imu)

IMU 传感器数据：
- `angular_velocity`: 机身角速度
- `orientation`: 机身姿态四元数

### `/joint_states` (sensor_msgs/JointState)

关节状态反馈：
- `position`: 23 个关节位置 (rad)
- `velocity`: 23 个关节速度 (rad/s)

## 发布的话题

### `/lowcmd` (unitree_legged_msgs/LowCmd)

低级控制指令，包含 23 个关节的：
- `mode`: 控制模式 (0x0A = 位置控制)
- `q`: 目标位置 (rad)
- `dq`: 目标速度 (rad/s)
- `Kp`: 比例增益
- `Kd`: 微分增益
- `tau`: 前馈力矩

## 测试

### 1. 发送测试速度命令

```bash
# 前进 0.5 m/s
rostopic pub /cmd_vel geometry_msgs/Twist \
  "linear:
    x: 0.5
    y: 0.0
    z: 0.0
  angular:
    x: 0.0
    y: 0.0
    z: 0.0" -r 10

# 停止
rostopic pub /cmd_vel geometry_msgs/Twist \
  "linear: {x: 0.0, y: 0.0, z: 0.0}
   angular: {x: 0.0, y: 0.0, z: 0.0}" -r 10
```

### 2. 监控话题

```bash
# 查看发布的低级指令
rostopic echo /lowcmd

# 检查频率
rostopic hz /lowcmd
# 应该输出 ~50 Hz

# 查看当前速度命令
rostopic echo /cmd_vel
```

### 3. 使用键盘控制

```bash
# 安装 teleop_twist_keyboard
sudo apt-get install ros-$ROS_DISTRO-teleop-twist-keyboard

# 运行键盘控制
rosrun teleop_twist_keyboard teleop_twist_keyboard.py cmd_vel:=/cmd_vel
```

## 故障排查

### 问题 1: 节点启动失败

**可能原因**: Python 环境未激活

```bash
conda activate unitree_rl_mjlab
python scripts/rl_policy_lowlevel_node.py
```

### 问题 2: "Waiting for sensor data"

**可能原因**: IMU 或关节状态话题未发布

```bash
# 检查话题
rostopic list | grep -E "imu|joint"

# 查看话题频率
rostopic hz /trunk_imu
rostopic hz /joint_states
```

### 问题 3: checkpoint 文件未找到

**解决方法**: 指定正确的路径

```bash
python scripts/rl_policy_lowlevel_node.py \
  _checkpoint_path:=/path/to/your/model_10000.pt
```

### 问题 4: unitree_legged_msgs 未找到

**解决方法**: 节点会自动回退到使用 JointState

如需安装 unitree_legged_msgs:
```bash
cd ~/catkin_ws/src
git clone https://github.com/unitreerobotics/unitree_ros_to_real.git
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

## 性能监控

### 查看节点信息

```bash
# 节点列表
rosnode list | grep rl_policy

# 节点信息
rosnode info /rl_policy_lowlevel

# 话题连接
rostopic info /lowcmd
```

### 性能指标

- 控制频率: ~50 Hz
- 推理延迟: < 1ms (GPU) 或 < 5ms (CPU)
- CPU 使用: ~5-10% (GPU 模式)
- 内存使用: ~2GB

## 与仿真环境集成

### MuJoCo 仿真

如果你的仿真环境订阅 `/lowcmd`，节点会直接与仿真通信：

```bash
# 终端1: 启动仿真
./your_simulation

# 终端2: 启动 RL Policy 节点
roslaunch unitree_rl_control rl_policy_lowlevel.launch

# 终端3: 发送速度命令
rostopic pub /cmd_vel geometry_msgs/Twist ...
```

### Gazebo 仿真

如果使用 Gazebo，可能需要话题重映射：

```bash
roslaunch unitree_rl_control rl_policy_lowlevel.launch \
  joint_states_topic:=/unitree_g1/joint_states \
  imu_topic:=/unitree_g1/imu
```

## 注意事项

1. **首次运行**: 节点会从当前关节状态初始化默认姿态
2. **安全措施**: 建议先在仿真中测试
3. **PD 参数**: Kp/Kd 需要根据实际机器人调整
4. **关节名称**: 确保与实际机器人的关节名称匹配

## 相关文档

- [PD_CONTROL_EXPLANATION.md](../PD_CONTROL_EXPLANATION.md) - PD 控制说明
- [ROS_INTEGRATION.md](../ROS_INTEGRATION.md) - ROS 集成详细方案
- [ROS_CHECKLIST.md](../ROS_CHECKLIST.md) - 对接清单

---

**文档版本**: v1.0  
**最后更新**: 2026-06-18
