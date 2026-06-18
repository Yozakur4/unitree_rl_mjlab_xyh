# ROS 包设置和使用说明

## 快速开始

### 1. 编译 ROS 消息

```bash
cd ~/unitree_RL/unitree_rl_mjlab

# 方法1: 使用提供的脚本（推荐）
bash /tmp/build_ros_msg.sh

# 方法2: 手动编译
# 创建或使用现有的 catkin workspace
cd ~/catkin_ws/src
ln -s ~/unitree_RL/unitree_rl_mjlab
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

### 2. 运行节点

```bash
# 激活 conda 环境
conda activate unitree_rl_mjlab

# Source ROS workspace
source ~/catkin_ws/devel/setup.bash

# 运行节点
rosrun unitree_rl_mjlab rl_policy_lowlevel_node.py \
  _checkpoint_path:=$HOME/unitree_RL/model_10000.pt
```

### 3. 发送速度命令

```bash
# 使用自定义 VelocityCommand 消息
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "vel_x: 0.5
   vel_y: 0.0
   yaw_rate: 0.0" -r 10
```

## 文件结构

```
unitree_rl_mjlab/
├── CMakeLists.txt           # ROS 包编译配置
├── package.xml              # ROS 包描述文件
├── msg/
│   └── VelocityCommand.msg  # 自定义速度命令消息
├── scripts/
│   ├── rl_policy_lowlevel_node.py  # 主节点脚本
│   ├── play.py
│   └── play_straight.py
├── launch/
│   └── rl_policy_lowlevel.launch
└── docs/
    └── RL_LOWLEVEL_NODE_USAGE.md
```

## VelocityCommand 消息

### 消息定义

```
float64 vel_x      # 前进速度 (m/s), 范围 [-1.0, 2.0]
float64 vel_y      # 横向速度 (m/s), 范围 [-1.0, 1.0]
float64 yaw_rate   # 旋转速度 (rad/s), 范围 [-1.0, 1.0]
```

### 使用示例

#### Python 发布

```python
#!/usr/bin/env python3
import rospy
from unitree_rl_mjlab.msg import VelocityCommand

rospy.init_node('velocity_commander')
pub = rospy.Publisher('/velocity_command', VelocityCommand, queue_size=10)

rate = rospy.Rate(10)  # 10 Hz
while not rospy.is_shutdown():
    cmd = VelocityCommand()
    cmd.vel_x = 0.5    # 前进 0.5 m/s
    cmd.vel_y = 0.0    # 无横向
    cmd.yaw_rate = 0.0 # 无旋转
    pub.publish(cmd)
    rate.sleep()
```

#### 命令行发布

```bash
# 前进
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.8, vel_y: 0.0, yaw_rate: 0.0}" -r 10

# 左移
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.0, vel_y: 0.5, yaw_rate: 0.0}" -r 10

# 原地旋转
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.0, vel_y: 0.0, yaw_rate: 0.5}" -r 10

# 停止
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.0, vel_y: 0.0, yaw_rate: 0.0}" -r 10
```

## 完整测试流程

### 终端 1: 启动仿真（假设你有）

```bash
# 启动你的仿真环境
./your_simulation
```

### 终端 2: 启动 RL Policy 节点

```bash
conda activate unitree_rl_mjlab
source ~/catkin_ws/devel/setup.bash

rosrun unitree_rl_mjlab rl_policy_lowlevel_node.py \
  _checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  _device:=cuda:0
```

### 终端 3: 发送速度命令

```bash
source ~/catkin_ws/devel/setup.bash

# 前进测试
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.5, vel_y: 0.0, yaw_rate: 0.0}" -r 10
```

### 终端 4: 监控

```bash
# 查看发布的低级指令
rostopic echo /lowcmd

# 查看频率
rostopic hz /lowcmd

# 查看节点信息
rosnode info /rl_policy_lowlevel
```

## 故障排查

### 问题: 找不到 VelocityCommand 消息类型

**解决方法**:

```bash
# 1. 确认消息已编译
ls ~/catkin_ws/devel/lib/python*/dist-packages/unitree_rl_mjlab/msg/

# 2. Source workspace
source ~/catkin_ws/devel/setup.bash

# 3. 验证消息可用
rosmsg show unitree_rl_mjlab/VelocityCommand
```

### 问题: 节点无法导入消息

**解决方法**:

```bash
# 确保 Python 路径包含 ROS workspace
export PYTHONPATH=$PYTHONPATH:~/catkin_ws/devel/lib/python3/dist-packages

# 或在脚本开头添加
import sys
sys.path.insert(0, '/home/user/catkin_ws/devel/lib/python3/dist-packages')
```

## 不使用 ROS 消息编译的替代方案

如果无法编译 ROS 消息，节点会自动回退到使用 `geometry_msgs/Twist`:

```bash
# 使用标准 Twist 消息
rostopic pub /cmd_vel geometry_msgs/Twist \
  "linear: {x: 0.5, y: 0.0, z: 0.0}
   angular: {x: 0.0, y: 0.0, z: 0.0}" -r 10
```

节点会自动检测并适配。

---

**相关文档**:
- [RL_LOWLEVEL_NODE_USAGE.md](RL_LOWLEVEL_NODE_USAGE.md) - 详细使用说明
- [ROS_INTEGRATION.md](../ROS_INTEGRATION.md) - ROS 集成方案
