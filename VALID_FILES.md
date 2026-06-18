# 有效文件清单

## 🎯 核心功能实现（必需）

### 1. ROS 节点主程序 ⭐⭐⭐
```
scripts/rl_policy_lowlevel_node.py
```
**功能**: 
- 订阅 VelocityCommand (vel_x, vel_y, yaw_rate)
- 订阅 IMU 和关节状态
- 运行 RL Policy 推理
- 发布 LowLevelCmd 关节指令

**使用方法**:
```bash
conda activate unitree_rl_mjlab
python scripts/rl_policy_lowlevel_node.py \
  _checkpoint_path:=$HOME/unitree_RL/model_10000.pt
```

---

### 2. 自定义消息定义 ⭐⭐⭐
```
msg/VelocityCommand.msg
```
**内容**:
```msg
float64 vel_x      # 前进速度 (m/s)
float64 vel_y      # 横向速度 (m/s)
float64 yaw_rate   # 旋转速度 (rad/s)
```

**需要编译**: 使用 catkin_make

---

### 3. ROS 包配置文件 ⭐⭐⭐
```
CMakeLists.txt
package.xml
```
**功能**: ROS 包的编译和依赖配置

---

### 4. Launch 文件 ⭐⭐
```
launch/rl_policy_lowlevel.launch
```
**功能**: 一键启动节点并配置参数

**使用方法**:
```bash
roslaunch unitree_rl_mjlab rl_policy_lowlevel.launch \
  checkpoint_path:=$HOME/unitree_RL/model_10000.pt
```

---

## 🧪 测试工具（推荐）

### 5. 速度命令发布器 ⭐⭐
```
scripts/velocity_commander.py
```
**功能**: 
- 自动发布测试速度命令
- 包含多个测试场景（站立、前进、横移、旋转、组合）

**使用方法**:
```bash
python scripts/velocity_commander.py
```

---

## 📚 文档（重要参考）

### 核心文档 ⭐⭐⭐
```
PROJECT_SUMMARY.md              # 项目总览（从这里开始）
INTEGRATION_GUIDE.md            # 完整技术规格
PD_CONTROL_EXPLANATION.md       # PD控制说明（解答输出是位置还是力矩）
```

### ROS 相关文档 ⭐⭐
```
ROS_INTEGRATION.md              # ROS 集成方案
ROS_CHECKLIST.md                # 与环境方对接清单
docs/RL_LOWLEVEL_NODE_USAGE.md  # 节点使用说明
docs/ROS_PACKAGE_SETUP.md       # ROS 包设置说明
```

### 快速参考 ⭐
```
QUICK_REFERENCE.md              # 参数速查表
```

### 训练相关
```
TRAINING_IMPROVEMENTS.md        # 训练改进建议（针对偏移问题）
```

---

## 🔧 其他测试脚本（可选）

这些脚本**不依赖 ROS**，用于直接测试模型：

```
scripts/play.py                 # 原始测试脚本（随机命令）
scripts/play_straight.py        # 固定速度命令测试
```

以下脚本有**依赖版本问题**，暂时不可用：
```
scripts/diagnose_straight_walk.py  # ❌ 有依赖问题
scripts/quick_test.py              # ❌ 有依赖问题
scripts/test_drift.sh              # ❌ 调用上述脚本
```

---

## 📂 完整文件树（有效部分）

```
unitree_rl_mjlab/
│
├── 🎯 ROS 实现（核心）
│   ├── scripts/
│   │   ├── rl_policy_lowlevel_node.py    ⭐⭐⭐ ROS 节点主程序
│   │   └── velocity_commander.py         ⭐⭐  测试工具
│   │
│   ├── msg/
│   │   └── VelocityCommand.msg           ⭐⭐⭐ 自定义消息
│   │
│   ├── launch/
│   │   └── rl_policy_lowlevel.launch     ⭐⭐  启动文件
│   │
│   ├── CMakeLists.txt                    ⭐⭐⭐ 编译配置
│   └── package.xml                       ⭐⭐⭐ 包描述
│
├── 📚 文档
│   ├── PROJECT_SUMMARY.md                ⭐⭐⭐ 从这里开始
│   ├── INTEGRATION_GUIDE.md              ⭐⭐⭐ 技术规格
│   ├── PD_CONTROL_EXPLANATION.md         ⭐⭐⭐ PD控制说明
│   ├── ROS_INTEGRATION.md                ⭐⭐  ROS方案
│   ├── ROS_CHECKLIST.md                  ⭐⭐  对接清单
│   ├── QUICK_REFERENCE.md                ⭐   参数速查
│   ├── TRAINING_IMPROVEMENTS.md          训练改进
│   └── docs/
│       ├── RL_LOWLEVEL_NODE_USAGE.md     节点使用说明
│       └── ROS_PACKAGE_SETUP.md          ROS包设置
│
└── 🧪 其他测试（可选）
    └── scripts/
        ├── play.py                       原始测试
        └── play_straight.py              固定速度测试
```

---

## 🚀 使用流程

### 步骤 1: 编译 ROS 消息（仅首次）

```bash
cd ~/unitree_RL/unitree_rl_mjlab

# 方法1: 使用编译脚本
bash /tmp/build_ros_msg.sh

# 方法2: 集成到 catkin workspace
cd ~/catkin_ws/src
ln -s ~/unitree_RL/unitree_rl_mjlab
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

### 步骤 2: 运行 ROS 节点

```bash
# 终端 1: 启动节点
conda activate unitree_rl_mjlab
source ~/catkin_ws/devel/setup.bash  # 如果编译了消息

python scripts/rl_policy_lowlevel_node.py \
  _checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  _device:=cuda:0
```

### 步骤 3: 发送速度命令

```bash
# 终端 2: 使用测试工具
python scripts/velocity_commander.py

# 或手动发布
rostopic pub /velocity_command unitree_rl_mjlab/VelocityCommand \
  "{vel_x: 0.8, vel_y: 0.0, yaw_rate: 0.0}" -r 10
```

---

## ⚡ 最小化使用（不编译消息）

如果不想编译 ROS 消息，节点会自动回退到使用标准 `geometry_msgs/Twist`:

```bash
# 运行节点（自动回退）
python scripts/rl_policy_lowlevel_node.py \
  _checkpoint_path:=$HOME/unitree_RL/model_10000.pt

# 使用标准 Twist 消息
rostopic pub /cmd_vel geometry_msgs/Twist \
  "linear: {x: 0.8, y: 0.0, z: 0.0}
   angular: {x: 0.0, y: 0.0, z: 0.0}" -r 10
```

---

## 📊 文件依赖关系

```
运行 ROS 节点需要:
  ✅ rl_policy_lowlevel_node.py    (必需)
  ✅ checkpoint 文件               (必需)
  ✅ VelocityCommand.msg           (推荐，可回退)
  ✅ CMakeLists.txt + package.xml  (如果编译消息)

测试需要:
  ✅ velocity_commander.py         (推荐)
  或 rostopic pub 命令

参考需要:
  ✅ PROJECT_SUMMARY.md
  ✅ INTEGRATION_GUIDE.md
  ✅ PD_CONTROL_EXPLANATION.md
```

---

## 总结

### 必需文件（3个）
1. `scripts/rl_policy_lowlevel_node.py` - 主程序
2. `msg/VelocityCommand.msg` - 消息定义
3. Checkpoint 文件 - `model_10000.pt`

### 推荐文件（5个）
4. `scripts/velocity_commander.py` - 测试工具
5. `CMakeLists.txt` - 编译配置
6. `package.xml` - 包描述
7. `launch/rl_policy_lowlevel.launch` - 启动文件
8. `PROJECT_SUMMARY.md` - 总览文档

### 其他都是文档和可选工具

---

**核心就是: 1个节点 + 1个消息 + 1个测试工具！**
