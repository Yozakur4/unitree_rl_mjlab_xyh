# ROS2 版本使用说明 (Unitree SDK2)

## ✅ 为宇树SDK2创建的ROS2版本

### 文件
```
scripts/rl_policy_lowlevel_node_ros2.py  # ROS2 版本节点
```

---

## 🆚 ROS1 vs ROS2 版本对比

| 特性 | ROS1 版本 | ROS2 版本 |
|------|----------|----------|
| 文件 | `rl_policy_lowlevel_node.py` | `rl_policy_lowlevel_node_ros2.py` |
| API | `rospy` | `rclpy` |
| 宇树SDK | SDK1 | SDK2 |
| 消息包 | `unitree_legged_msgs` | `unitree_go` |
| 参数 | `rospy.get_param()` | `node.declare_parameter()` |
| QoS | 自动 | 需要配置 |

---

## 📥 安装依赖

### 1. ROS2 环境
```bash
# Ubuntu 20.04
sudo apt install ros-foxy-desktop

# Ubuntu 22.04
sudo apt install ros-humble-desktop

source /opt/ros/foxy/setup.bash  # 或 humble
```

### 2. 宇树SDK2消息
```bash
# 克隆宇树ROS2包
cd ~/ros2_ws/src
git clone https://github.com/unitreerobotics/unitree_ros2.git

# 或者单独消息包
git clone https://github.com/unitreerobotics/unitree_go_msgs.git

cd ~/ros2_ws
colcon build
source install/setup.bash
```

### 3. Python依赖
```bash
conda activate unitree_rl_mjlab
pip install rclpy
```

---

## 🚀 使用方法

### 启动节点

```bash
# 激活环境
conda activate unitree_rl_mjlab
source /opt/ros/foxy/setup.bash  # 或 humble
source ~/ros2_ws/install/setup.bash

# 运行ROS2节点
python3 scripts/rl_policy_lowlevel_node_ros2.py \
  --ros-args \
  -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  -p device:=cuda:0 \
  -p control_rate:=50 \
  -p Kp:=50.0 \
  -p Kd:=1.0
```

### 发送速度命令

```bash
# 使用 ROS2 命令行
ros2 topic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.8, vel_y: 0.0, yaw_rate: 0.0}" --rate 10

# 或使用标准 Twist
ros2 topic pub /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.8, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" --rate 10
```

### 监控话题

```bash
# 查看话题列表
ros2 topic list

# 查看话题频率
ros2 topic hz /lowcmd
ros2 topic hz /trunk_imu
ros2 topic hz /joint_states

# 查看话题内容
ros2 topic echo /lowcmd
```

---

## 🔧 ROS2 特有配置

### QoS 配置

ROS2 需要配置 QoS (Quality of Service)，脚本中已配置：

```python
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

qos_profile = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10
)
```

**如果遇到话题不通的问题**，可能需要调整 QoS：

```python
# 宽松配置（用于调试）
qos_profile = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=10
)
```

---

## 📋 宇树SDK2消息格式

### LowCmd 消息结构
```python
# unitree_go/msg/LowCmd.msg
uint8[40] motor_cmd  # 最多40个电机

# unitree_go/msg/MotorCmd.msg
uint8 mode      # 控制模式 0x0A=位置控制
float32 q       # 目标位置 (rad)
float32 dq      # 目标速度 (rad/s)
float32 tau     # 前馈力矩 (Nm)
float32 kp      # 比例增益
float32 kd      # 微分增益
```

**关键差异（SDK1 vs SDK2）**:
- SDK1: `motorCmd` (数组)
- SDK2: `motor_cmd` (数组，使用下划线)

---

## 🔄 从ROS1迁移

如果你之前使用 ROS1 版本，主要差异：

### API 变化
```python
# ROS1                          # ROS2
import rospy              →     import rclpy
                                from rclpy.node import Node

rospy.init_node()         →     rclpy.init()
                                node = Node('name')

rospy.Subscriber()        →     node.create_subscription()
rospy.Publisher()         →     node.create_publisher()
rospy.Timer()            →     node.create_timer()
rospy.spin()             →     rclpy.spin(node)
rospy.loginfo()          →     node.get_logger().info()
rospy.get_param()        →     node.declare_parameter()
                                node.get_parameter()
```

### 命令行变化
```bash
# ROS1                          # ROS2
roscore                   →     (不需要)
rosrun                    →     ros2 run
roslaunch                 →     ros2 launch
rostopic list             →     ros2 topic list
rostopic echo             →     ros2 topic echo
rostopic pub              →     ros2 topic pub
rosnode list              →     ros2 node list
```

---

## 🧪 测试流程

### 1. 检查宇树SDK2话题
```bash
ros2 topic list | grep -E "trunk_imu|joint_states|lowcmd"
```

应该看到：
```
/trunk_imu
/joint_states
/lowcmd (如果仿真已经在监听)
```

### 2. 检查消息类型
```bash
ros2 topic info /trunk_imu
ros2 topic info /joint_states
```

### 3. 启动节点
```bash
python3 scripts/rl_policy_lowlevel_node_ros2.py \
  --ros-args \
  -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt
```

### 4. 检查节点运行
```bash
ros2 node list
# 应该看到: /rl_policy_lowlevel_node

ros2 node info /rl_policy_lowlevel_node
```

### 5. 发送测试命令
```bash
ros2 topic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.3, vel_y: 0.0, yaw_rate: 0.0}" --rate 10
```

---

## ⚠️ 常见问题

### 问题 1: 找不到 unitree_go 消息
```bash
# 错误
ModuleNotFoundError: No module named 'unitree_go'

# 解决
cd ~/ros2_ws/src
git clone https://github.com/unitreerobotics/unitree_go_msgs.git
cd ~/ros2_ws
colcon build
source install/setup.bash
```

### 问题 2: QoS 不匹配
```bash
# 错误
[WARN] New subscription discovered..., but QoS is incompatible

# 解决
在脚本中修改 QoS 配置，使用 BEST_EFFORT
```

### 问题 3: 话题没有数据
```bash
# 检查发布者
ros2 topic info /trunk_imu

# 应该显示发布者数量 > 0
```

### 问题 4: 参数不生效
```bash
# ROS2 参数格式不同
# 错误
python script.py _param:=value

# 正确
python script.py --ros-args -p param:=value
```

---

## 📦 完整启动示例

### 终端 1: 启动仿真（假设）
```bash
source /opt/ros/foxy/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch unitree_simulation g1_simulation.launch.py
```

### 终端 2: 启动 RL Policy 节点
```bash
conda activate unitree_rl_mjlab
source /opt/ros/foxy/setup.bash
source ~/ros2_ws/install/setup.bash

python3 scripts/rl_policy_lowlevel_node_ros2.py \
  --ros-args \
  -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  -p device:=cuda:0
```

### 终端 3: 发送速度命令
```bash
source /opt/ros/foxy/setup.bash

# 前进
ros2 topic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.5, vel_y: 0.0, yaw_rate: 0.0}" --rate 10

# 停止
ros2 topic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.0, vel_y: 0.0, yaw_rate: 0.0}" --rate 10
```

### 终端 4: 监控
```bash
source /opt/ros/foxy/setup.bash

# 查看频率
ros2 topic hz /lowcmd

# 查看内容
ros2 topic echo /lowcmd
```

---

## 🔍 验证清单

- [ ] ROS2 环境已安装并 source
- [ ] 宇树 SDK2 消息包已安装
- [ ] conda 环境已激活
- [ ] checkpoint 文件存在
- [ ] `/trunk_imu` 话题有数据
- [ ] `/joint_states` 话题有数据
- [ ] 节点成功启动
- [ ] `/lowcmd` 话题在发布

---

## 📊 性能对比

| 指标 | ROS1 | ROS2 |
|------|------|------|
| 延迟 | ~20ms | ~15ms |
| 通信 | TCP/UDP | DDS |
| 实时性 | 中等 | 更好 |
| 兼容性 | 广泛 | 较新 |

---

## 相关文档

- [ROS_BRIDGE_COMPATIBILITY.md](../ROS_BRIDGE_COMPATIBILITY.md) - ROS1/ROS2对比
- [INTERFACE_SPEC.md](../INTERFACE_SPEC.md) - 接口规格
- [VALID_FILES.md](../VALID_FILES.md) - 文件清单

---

**版本**: ROS2 Foxy / Humble  
**宇树SDK**: SDK2  
**更新日期**: 2026-06-18
