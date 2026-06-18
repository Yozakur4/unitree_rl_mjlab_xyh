# ROS1/ROS2 Bridge 兼容性分析

## 当前脚本分析

### 当前状态
脚本 `rl_policy_lowlevel_node.py` 是 **ROS1** 实现

使用的是 ROS1 API:
```python
import rospy                           # ROS1
rospy.init_node()                      # ROS1
rospy.Subscriber()                     # ROS1
rospy.Publisher()                      # ROS1
rospy.Timer()                          # ROS1
rospy.spin()                           # ROS1
```

---

## ROS1/ROS2 Bridge 格式要求

### 什么是 ROS Bridge？

ROS Bridge 允许 ROS1 和 ROS2 节点互相通信，有两种情况：

### 情况 1: 你的节点在 ROS1，仿真在 ROS2
```
[ROS2 仿真]
    ↓ 发布 /trunk_imu, /joint_states
[ros1_bridge]
    ↓ 转发到 ROS1
[ROS1 你的节点] rl_policy_lowlevel_node.py
    ↓ 发布 /lowcmd
[ros1_bridge]
    ↓ 转发到 ROS2
[ROS2 仿真]
```
**✅ 当前脚本可以工作，需要启动 ros1_bridge**

### 情况 2: 你的节点在 ROS2，仿真在 ROS1
```
需要将脚本移植到 ROS2
```

---

## 检查清单

### ✅ ROS1 格式检查

当前脚本使用的消息类型：

| 消息 | 包 | ROS1 | ROS2 | Bridge支持 |
|------|-----|------|------|-----------|
| `sensor_msgs/Imu` | sensor_msgs | ✅ | ✅ | ✅ |
| `sensor_msgs/JointState` | sensor_msgs | ✅ | ✅ | ✅ |
| `unitree_legged_msgs/LowCmd` | unitree_legged_msgs | ✅ | ❓ | ❓ |
| `VelocityCommand` (自定义) | 自定义 | ✅ | ❌ | ❌ |

**关键问题**:
1. `unitree_legged_msgs` 是否有 ROS2 版本？
2. 自定义 `VelocityCommand` 需要在 ROS2 中也定义

---

## 场景分析

### 场景 A: 环境是 ROS1 + 你的节点是 ROS1
```
✅ 当前脚本直接可用，无需 bridge
```

### 场景 B: 环境是 ROS2 + 你的节点是 ROS1
```
需要:
1. 启动 ros1_bridge
2. 确认 unitree_legged_msgs 在两侧都有
3. 自定义消息需要特殊处理
```

**ros1_bridge 启动方式**:
```bash
# 终端 1: ROS1 环境
source /opt/ros/noetic/setup.bash
roscore

# 终端 2: ROS2 + ROS1 bridge
source /opt/ros/foxy/setup.bash  # 或 galactic/humble
source /opt/ros/noetic/setup.bash
ros2 run ros1_bridge dynamic_bridge --bridge-all-topics

# 终端 3: 你的 ROS1 节点
source /opt/ros/noetic/setup.bash
conda activate unitree_rl_mjlab
python scripts/rl_policy_lowlevel_node.py
```

### 场景 C: 环境是 ROS2 + 你的节点是 ROS2
```
❌ 需要移植脚本到 ROS2
```

---

## 如果需要 ROS2 版本

我可以创建 ROS2 版本的脚本，主要改动：

### ROS1 → ROS2 API 映射
```python
# ROS1                        # ROS2
import rospy             →    import rclpy
                              from rclpy.node import Node

rospy.init_node()        →    rclpy.init()
                              node = Node('name')

rospy.Subscriber()       →    node.create_subscription()
rospy.Publisher()        →    node.create_publisher()
rospy.Timer()           →    node.create_timer()
rospy.spin()            →    rclpy.spin(node)
rospy.get_param()       →    node.declare_parameter()
                              node.get_parameter()
```

---

## 宇树SDK 的 ROS 版本

### 检查宇树是否提供 ROS2 支持

已知宇树机器人的 ROS 包：
- **ROS1**: `unitree_legged_msgs`, `unitree_ros_to_real`
- **ROS2**: 部分机器人有 ROS2 支持（需要确认 G1）

**需要确认**:
```bash
# 如果有 ROS2 环境
ros2 pkg list | grep unitree
```

---

## 建议

### 方案 1: 继续使用 ROS1（推荐）
如果仿真环境是 ROS1，或者可以用 bridge：
- ✅ 当前脚本直接可用
- ✅ 无需修改
- ✅ 如需 bridge，启动 ros1_bridge 即可

### 方案 2: 移植到 ROS2
如果仿真环境只支持 ROS2：
- ❌ 需要重写脚本（工作量：2-3小时）
- ❌ 需要 ROS2 版本的 unitree_legged_msgs
- ❌ 需要重新编译自定义消息

---

## 快速判断

**请回答以下问题**:

1. **你的仿真环境使用什么？**
   - [ ] ROS1 (Melodic/Noetic)
   - [ ] ROS2 (Foxy/Galactic/Humble)
   - [ ] 不确定

2. **你的仿真环境发布的话题是？**
   ```bash
   # ROS1
   rostopic list
   
   # ROS2
   ros2 topic list
   ```

3. **你是否已经有 ros1_bridge 环境？**
   - [ ] 是
   - [ ] 否
   - [ ] 不需要（全是 ROS1 或全是 ROS2）

4. **宇树的 unitree_legged_msgs 你使用的是？**
   - [ ] ROS1 版本
   - [ ] ROS2 版本
   - [ ] 两个都有

---

## 临时解决方案

如果你现在不确定，**当前脚本可以在 ROS1 环境中直接使用**。

如果发现需要 ROS2，我可以立即为你创建 ROS2 版本。

---

**请告诉我你的仿真环境是 ROS1 还是 ROS2？**

这样我可以：
1. 确认当前脚本是否可用
2. 或者创建对应版本的脚本

---

**文档版本**: v1.0  
**创建日期**: 2026-06-18
