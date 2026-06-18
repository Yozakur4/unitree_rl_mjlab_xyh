# 选择正确的版本 - ROS1 vs ROS2

## 快速判断

### 你应该使用哪个版本？

```
问：你的宇树机器人使用什么SDK？
  ├─ SDK1 (ROS1) → 使用 rl_policy_lowlevel_node.py
  └─ SDK2 (ROS2) → 使用 rl_policy_lowlevel_node_ros2.py ✅

问：你运行什么命令查看话题？
  ├─ rostopic list → ROS1 版本
  └─ ros2 topic list → ROS2 版本 ✅

问：你的仿真环境？
  ├─ Gazebo Classic → ROS1
  └─ Gazebo Ignition → ROS2 ✅
```

---

## 🔍 快速测试

### 在终端运行
```bash
# 如果这个命令有效 → ROS1
rostopic list

# 如果这个命令有效 → ROS2
ros2 topic list
```

---

## 📊 两个版本对比

| 特性 | ROS1 版本 | ROS2 版本 |
|------|----------|----------|
| **文件** | `rl_policy_lowlevel_node.py` | `rl_policy_lowlevel_node_ros2.py` |
| **宇树SDK** | SDK1 | SDK2 ✅ |
| **消息包** | `unitree_legged_msgs` | `unitree_go` ✅ |
| **Python API** | `rospy` | `rclpy` |
| **参数格式** | `_param:=value` | `--ros-args -p param:=value` |
| **话题命令** | `rostopic` | `ros2 topic` |
| **QoS** | 自动 | 需配置 |

---

## 📝 使用方法

### ROS1 版本
```bash
# 运行
python scripts/rl_policy_lowlevel_node.py \
  _checkpoint_path:=$HOME/unitree_RL/model_10000.pt

# 发送命令
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.5, vel_y: 0.0, yaw_rate: 0.0}" -r 10

# 监控
rostopic hz /lowcmd
```

### ROS2 版本 ✅
```bash
# 运行
python3 scripts/rl_policy_lowlevel_node_ros2.py \
  --ros-args \
  -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt

# 发送命令
ros2 topic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.5, vel_y: 0.0, yaw_rate: 0.0}" --rate 10

# 监控
ros2 topic hz /lowcmd
```

---

## 🎯 核心差异

### 1. 消息结构

#### ROS1 (SDK1)
```python
from unitree_legged_msgs.msg import LowCmd, MotorCmd

lowcmd.motorCmd[i] = motor_cmd  # 使用 motorCmd
```

#### ROS2 (SDK2) ✅
```python
from unitree_go.msg import LowCmd, MotorCmd

lowcmd.motor_cmd[i] = motor_cmd  # 使用 motor_cmd (下划线)
```

### 2. 参数设置

#### ROS1
```python
import rospy
param = rospy.get_param('~param_name', default_value)
```

#### ROS2 ✅
```python
from rclpy.node import Node
self.declare_parameter('param_name', default_value)
param = self.get_parameter('param_name').value
```

### 3. 日志输出

#### ROS1
```python
rospy.loginfo("message")
rospy.logwarn("warning")
```

#### ROS2 ✅
```python
self.get_logger().info("message")
self.get_logger().warn("warning")
```

---

## 🔄 功能完全相同

两个版本实现的功能完全一致：

- ✅ 订阅速度命令 (VelocityCommand)
- ✅ 订阅 IMU 数据 (/trunk_imu)
- ✅ 订阅关节状态 (/joint_states)
- ✅ 运行 RL Policy (50Hz)
- ✅ 发布 LowCmd 关节指令
- ✅ 自动初始化默认姿态
- ✅ 支持消息回退机制

---

## 📦 依赖安装

### ROS1
```bash
sudo apt install ros-noetic-desktop
pip install rospy
```

### ROS2 ✅
```bash
sudo apt install ros-foxy-desktop  # 或 humble
pip install rclpy
```

---

## 🚀 推荐使用

### 如果你使用宇树SDK2 → ROS2版本 ✅

**理由**：
1. SDK2 是宇树的新版本
2. ROS2 性能更好
3. 未来趋势

**文件**：
- `scripts/rl_policy_lowlevel_node_ros2.py`
- 文档：`docs/ROS2_USAGE.md`

### 如果你使用宇树SDK1 → ROS1版本

**理由**：
1. 兼容旧版SDK
2. 更广泛的社区支持
3. 稳定成熟

**文件**：
- `scripts/rl_policy_lowlevel_node.py`
- 文档：`docs/RL_LOWLEVEL_NODE_USAGE.md`

---

## 📚 相关文档

### ROS2 版本 ✅
- [docs/ROS2_USAGE.md](docs/ROS2_USAGE.md) - ROS2详细使用说明
- [ROS_BRIDGE_COMPATIBILITY.md](ROS_BRIDGE_COMPATIBILITY.md) - 兼容性分析

### ROS1 版本
- [docs/RL_LOWLEVEL_NODE_USAGE.md](docs/RL_LOWLEVEL_NODE_USAGE.md) - ROS1使用说明
- [INTERFACE_SPEC.md](INTERFACE_SPEC.md) - 接口规格

### 通用文档
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - 项目总览
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - 技术规格
- [PD_CONTROL_EXPLANATION.md](PD_CONTROL_EXPLANATION.md) - PD控制说明

---

## ✅ 总结

**对于宇树SDK2用户**（你的情况）：

```bash
✅ 使用文件: scripts/rl_policy_lowlevel_node_ros2.py
✅ 阅读文档: docs/ROS2_USAGE.md
✅ 命令格式: ros2 topic ...
✅ 消息包: unitree_go
```

**两个版本功能完全相同，只是适配不同的ROS版本！**

---

**文档版本**: v1.0  
**更新日期**: 2026-06-18
