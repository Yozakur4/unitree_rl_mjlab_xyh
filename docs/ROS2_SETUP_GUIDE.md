# ROS2 环境设置指南

## 📦 安装 ROS2

### Ubuntu 20.04 → ROS2 Foxy
```bash
# 设置源
sudo apt update && sudo apt install curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 安装 ROS2
sudo apt update
sudo apt install ros-foxy-desktop python3-argcomplete

# 安装开发工具
sudo apt install ros-dev-tools
```

### Ubuntu 22.04 → ROS2 Humble
```bash
# 设置源
sudo apt update && sudo apt install curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 安装 ROS2
sudo apt update
sudo apt install ros-humble-desktop python3-argcomplete

# 安装开发工具
sudo apt install ros-dev-tools
```

---

## 🐍 创建 Conda 环境（推荐）

### 方案 1: 新建 ROS2 专用环境
```bash
# 创建新环境（Python 3.8-3.10，ROS2 Foxy/Humble 兼容）
conda create -n unitree_rl_ros2 python=3.10

# 激活环境
conda activate unitree_rl_ros2

# 安装基础依赖
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install numpy

# 安装 ROS2 Python 包
pip install rclpy
```

### 方案 2: 在现有环境中添加 ROS2
```bash
# 激活现有环境
conda activate unitree_rl_mjlab

# 安装 rclpy（可能会有兼容性问题）
pip install rclpy
```

**注意**: ROS2 的系统安装和 conda 环境可以共存

---

## 🔧 配置环境

### 1. 设置 ROS2 环境变量

在 `~/.bashrc` 中添加：
```bash
# ROS2 Foxy (Ubuntu 20.04)
source /opt/ros/foxy/setup.bash

# 或 ROS2 Humble (Ubuntu 22.04)
source /opt/ros/humble/setup.bash

# 自动补全
source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash
```

或每次手动 source：
```bash
source /opt/ros/foxy/setup.bash  # 或 humble
```

### 2. 创建 ROS2 工作空间

```bash
# 创建工作空间
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws

# 初始化
colcon build
source install/setup.bash
```

---

## 📦 安装宇树 SDK2 消息

### 方法 1: 从源码编译
```bash
cd ~/ros2_ws/src

# 克隆宇树 ROS2 包
git clone https://github.com/unitreerobotics/unitree_ros2.git

# 或者只克隆消息包
git clone https://github.com/unitreerobotics/unitree_go.git

# 编译
cd ~/ros2_ws
colcon build --packages-select unitree_go

# Source
source install/setup.bash
```

### 方法 2: 检查是否已安装
```bash
# 检查 unitree_go 消息
ros2 pkg list | grep unitree
ros2 interface list | grep unitree
```

---

## 🧪 验证安装

### 1. 验证 ROS2
```bash
# 检查 ROS2 版本
printenv | grep ROS

# 应该看到
ROS_VERSION=2
ROS_DISTRO=foxy  # 或 humble
ROS_PYTHON_VERSION=3
```

### 2. 验证 rclpy
```bash
python3 -c "import rclpy; print('rclpy OK')"
```

### 3. 验证宇树消息
```bash
# 检查消息类型
ros2 interface show unitree_go/msg/LowCmd
ros2 interface show unitree_go/msg/MotorCmd
```

### 4. 验证 RL Policy 环境
```bash
conda activate unitree_rl_mjlab  # 或 unitree_rl_ros2
python3 -c "import torch; import mjlab; print('RL环境 OK')"
```

---

## 🚀 运行测试

### 完整启动脚本

创建 `test_ros2_node.sh`:
```bash
#!/bin/bash

echo "=========================================="
echo "ROS2 节点测试脚本"
echo "=========================================="
echo ""

# 1. Source ROS2
echo "[1/4] Source ROS2 环境..."
source /opt/ros/foxy/setup.bash  # 或 humble
source ~/ros2_ws/install/setup.bash

# 2. 激活 Conda 环境
echo "[2/4] 激活 Conda 环境..."
eval "$(conda shell.bash hook)"
conda activate unitree_rl_mjlab  # 或 unitree_rl_ros2

# 3. 检查依赖
echo "[3/4] 检查依赖..."
python3 << 'EOF'
try:
    import rclpy
    print("  ✓ rclpy")
except:
    print("  ✗ rclpy 未安装")
    exit(1)

try:
    import torch
    print("  ✓ torch")
except:
    print("  ✗ torch 未安装")
    exit(1)

try:
    import mjlab
    print("  ✓ mjlab")
except:
    print("  ✗ mjlab 未安装")
    exit(1)

print("")
EOF

# 4. 运行节点
echo "[4/4] 启动 ROS2 节点..."
python3 scripts/rl_policy_lowlevel_node_ros2.py \
  --ros-args \
  -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  -p device:=cuda:0 \
  -p control_rate:=50

echo ""
echo "节点已停止"
```

使用：
```bash
chmod +x test_ros2_node.sh
./test_ros2_node.sh
```

---

## ⚠️ 常见问题

### 问题 1: rclpy 安装失败
```bash
# 原因：Python 版本不兼容
# 解决：使用 Python 3.8-3.10

# 重新创建环境
conda create -n unitree_rl_ros2 python=3.10
conda activate unitree_rl_ros2
pip install rclpy
```

### 问题 2: 找不到 ROS2 命令
```bash
# 确保已 source
source /opt/ros/foxy/setup.bash

# 或添加到 ~/.bashrc
echo "source /opt/ros/foxy/setup.bash" >> ~/.bashrc
```

### 问题 3: unitree_go 消息未找到
```bash
# 编译消息包
cd ~/ros2_ws
colcon build --packages-select unitree_go
source install/setup.bash

# 验证
ros2 interface list | grep unitree
```

### 问题 4: Conda 和 ROS2 冲突
```bash
# 先 source ROS2，再激活 conda
source /opt/ros/foxy/setup.bash
conda activate unitree_rl_mjlab
```

---

## 📋 快速启动清单

开发环境准备：
- [ ] Ubuntu 20.04/22.04 安装完成
- [ ] ROS2 (Foxy/Humble) 已安装
- [ ] Conda 环境已创建
- [ ] rclpy 已安装
- [ ] PyTorch 已安装
- [ ] mjlab 可导入
- [ ] unitree_go 消息已编译
- [ ] checkpoint 文件存在

每次启动需要：
```bash
# 1. Source ROS2
source /opt/ros/foxy/setup.bash
source ~/ros2_ws/install/setup.bash

# 2. 激活 Conda
conda activate unitree_rl_mjlab

# 3. 运行节点
python3 scripts/rl_policy_lowlevel_node_ros2.py \
  --ros-args -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt
```

---

## 💡 推荐配置

### 创建启动别名

在 `~/.bashrc` 添加：
```bash
# ROS2 环境
alias ros2_setup='source /opt/ros/foxy/setup.bash && source ~/ros2_ws/install/setup.bash'

# RL Policy 环境
alias rl_ros2='ros2_setup && conda activate unitree_rl_mjlab'

# 快速启动节点
alias rl_node='rl_ros2 && cd ~/unitree_RL/unitree_rl_mjlab && python3 scripts/rl_policy_lowlevel_node_ros2.py --ros-args -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt'
```

使用：
```bash
source ~/.bashrc
rl_node  # 一键启动
```

---

## 🔍 调试模式

如果遇到问题，使用详细日志：
```bash
# 设置 ROS2 日志级别
export RCUTILS_CONSOLE_OUTPUT_FORMAT="[{severity}] [{name}]: {message}"
export RCUTILS_LOGGING_USE_STDOUT=1
export RCUTILS_LOGGING_BUFFERED_STREAM=1

# 运行节点
python3 scripts/rl_policy_lowlevel_node_ros2.py \
  --ros-args \
  -p checkpoint_path:=$HOME/unitree_RL/model_10000.pt \
  --log-level debug
```

---

## 📚 相关资源

- [ROS2 官方文档](https://docs.ros.org/en/foxy/)
- [rclpy API](https://docs.ros2.org/foxy/api/rclpy/)
- [宇树机器人 ROS2](https://github.com/unitreerobotics/unitree_ros2)

---

**完成这些步骤后，你就可以测试 ROS2 节点了！**

如果遇到问题，告诉我具体的错误信息，我可以帮你解决。
