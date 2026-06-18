# ROS 集成对接清单

## 📋 需要环境方确认的信息

### 1. ROS 话题接口

```yaml
# 请环境方填写实际的话题名称和消息类型

IMU数据:
  话题名称: /unitree_g1/imu  # 请确认
  消息类型: sensor_msgs/Imu  # 请确认
  频率: _____ Hz

关节状态反馈:
  话题名称: /unitree_g1/joint_states  # 请确认
  消息类型: sensor_msgs/JointState    # 请确认
  频率: _____ Hz

关节指令输入:
  话题名称: /unitree_g1/joint_commands  # 请确认
  消息类型: sensor_msgs/JointState      # 请确认
  控制模式: [ ] 位置控制  [ ] 速度控制  [ ] 力矩控制

速度命令输入:
  话题名称: /cmd_vel              # 请确认
  消息类型: geometry_msgs/Twist  # 请确认
```

### 2. 关节名称和顺序

**请环境方提供准确的关节名称列表（必须按顺序）：**

```python
# RL Policy 输出的 23 个关节按以下顺序：
# [0-5]   左腿 6个
# [6-11]  右腿 6个
# [12-14] 腰部 3个
# [15-18] 左臂 4个
# [19-22] 右臂 4个

joint_names = [
    # 左腿 (请填写实际名称)
    "left_hip_pitch_joint",      # 索引 0
    "left_hip_roll_joint",       # 索引 1
    "left_hip_yaw_joint",        # 索引 2
    "left_knee_joint",           # 索引 3
    "left_ankle_pitch_joint",    # 索引 4
    "left_ankle_roll_joint",     # 索引 5
    
    # 右腿 (请填写实际名称)
    "right_hip_pitch_joint",     # 索引 6
    "right_hip_roll_joint",      # 索引 7
    "right_hip_yaw_joint",       # 索引 8
    "right_knee_joint",          # 索引 9
    "right_ankle_pitch_joint",   # 索引 10
    "right_ankle_roll_joint",    # 索引 11
    
    # 腰部 (请填写实际名称)
    "waist_yaw_joint",           # 索引 12
    "waist_roll_joint",          # 索引 13  (可能是 waist_pitch?)
    "waist_pitch_joint",         # 索引 14  (可能是 waist_roll?)
    
    # 左臂 (请填写实际名称)
    "left_shoulder_pitch_joint", # 索引 15
    "left_shoulder_roll_joint",  # 索引 16
    "left_shoulder_yaw_joint",   # 索引 17
    "left_elbow_joint",          # 索引 18
    
    # 右臂 (请填写实际名称)
    "right_shoulder_pitch_joint",# 索引 19
    "right_shoulder_roll_joint", # 索引 20
    "right_shoulder_yaw_joint",  # 索引 21
    "right_elbow_joint",         # 索引 22
]
```

**验证方法**:
```bash
# 运行以下命令查看实际的关节名称
rostopic echo /unitree_g1/joint_states -n1
```

### 3. 默认站立姿态

**请环境方提供机器人站立时的关节角度（23个值，单位：弧度）：**

```python
# 方法1: 让机器人站立，然后运行
rostopic echo /unitree_g1/joint_states -n1

# 方法2: 从URDF/配置文件中获取

default_joint_positions = [
    # 左腿 (rad)
    0.0,  # left_hip_pitch
    0.0,  # left_hip_roll
    0.0,  # left_hip_yaw
    0.0,  # left_knee
    0.0,  # left_ankle_pitch
    0.0,  # left_ankle_roll
    
    # 右腿 (rad)
    0.0,  # right_hip_pitch
    0.0,  # right_hip_roll
    0.0,  # right_hip_yaw
    0.0,  # right_knee
    0.0,  # right_ankle_pitch
    0.0,  # right_ankle_roll
    
    # 腰部 (rad)
    0.0,  # waist_yaw
    0.0,  # waist_roll
    0.0,  # waist_pitch
    
    # 左臂 (rad)
    0.0,  # left_shoulder_pitch
    0.0,  # left_shoulder_roll
    0.0,  # left_shoulder_yaw
    0.0,  # left_elbow
    
    # 右臂 (rad)
    0.0,  # right_shoulder_pitch
    0.0,  # right_shoulder_roll
    0.0,  # right_shoulder_yaw
    0.0,  # right_elbow
]
```

### 4. 关节限位

**请环境方提供每个关节的运动范围：**

```python
# 位置限制 (rad)
joint_position_lower = [___] * 23  # 下限
joint_position_upper = [___] * 23  # 上限

# 速度限制 (rad/s)
joint_velocity_limit = [___] * 23

# 力矩限制 (Nm) - 如果需要
joint_torque_limit = [___] * 23
```

### 5. 动作缩放系数

**请环境方确认或提供：**

```python
# RL Policy 输出 action ∈ [-1, 1]
# 实际关节位置 = default_pos + action * scale

# 需要确认每个关节的缩放系数
action_scale = [
    # 左腿
    0.25, 0.25, 0.25, 0.25, 0.25, 0.25,
    # 右腿
    0.25, 0.25, 0.25, 0.25, 0.25, 0.25,
    # 腰部
    0.25, 0.25, 0.25,
    # 左臂
    0.25, 0.25, 0.25, 0.25,
    # 右臂
    0.25, 0.25, 0.25, 0.25,
]

# 或者使用统一的缩放系数
action_scale_uniform = 0.25  # 请确认
```

**获取方法**: 从训练配置中查看 `G1_23DOF_ACTION_SCALE`
```bash
grep -r "G1_23DOF_ACTION_SCALE" src/assets/robots/
```

### 6. 坐标系定义

**请环境方确认坐标系：**

```yaml
机身坐标系 (Base Frame):
  X轴: [ ] 前  [ ] 后  [ ] 左  [ ] 右
  Y轴: [ ] 前  [ ] 后  [ ] 左  [ ] 右
  Z轴: [ ] 上  [ ] 下
  
IMU坐标系:
  [ ] 与机身坐标系对齐
  [ ] 需要坐标变换: _______________

重力方向:
  世界坐标系中重力: [0, 0, -1]  # 请确认
```

### 7. 控制接口细节

```yaml
控制模式:
  [ ] 位置控制: target_position
  [ ] 速度控制: target_velocity  
  [ ] 力矩控制: target_effort
  [ ] 混合模式: _______________

PD参数 (如果是位置控制):
  P增益: [___] * 23
  D增益: [___] * 23
  
更新频率:
  期望: 50 Hz
  实际: _____ Hz
  
延迟:
  传感器->ROS: _____ ms
  ROS->执行器: _____ ms
```

---

## 📤 向环境方说明的 RL Policy 规格

### 输入: 速度命令 (Twist Command)

```yaml
消息类型: geometry_msgs/Twist
维度: 3
范围:
  linear.x:  [-1.0, 2.0] m/s   # 前进速度（负值后退）
  linear.y:  [-1.0, 1.0] m/s   # 横向速度（正值向左）
  angular.z: [-1.0, 1.0] rad/s # 旋转速度（正值逆时针）

说明:
  - 超出范围的命令会被自动裁剪
  - 模型在这些范围内训练，超出范围可能表现不佳
```

### 输出: 关节位置指令

```yaml
维度: 23个关节
类型: 位置偏移量 (相对于默认姿态)
范围: 每个关节的 action ∈ [-1, 1]

转换公式:
  target_position[i] = default_position[i] + action[i] * action_scale[i]

更新频率: 50 Hz (每 20ms)
延迟: < 1ms (策略推理时间)
```

### 需要的传感器反馈

```yaml
1. IMU数据 (sensor_msgs/Imu):
   - angular_velocity: 机身角速度 (rad/s)
   - orientation: 机身姿态四元数
   - 频率: ≥ 100 Hz (推荐)

2. 关节状态 (sensor_msgs/JointState):
   - position: 23个关节位置 (rad)
   - velocity: 23个关节速度 (rad/s)
   - 频率: ≥ 50 Hz
```

### 性能要求

```yaml
控制频率: 50 Hz (固定)
推理延迟: < 1ms (GPU) 或 < 5ms (CPU)
总延迟预算: < 20ms

计算资源:
  GPU: NVIDIA RTX 2060 或更高 (推荐)
  CPU: 可运行但延迟较高
  内存: ~2GB (加载模型)
```

---

## ✅ 集成测试清单

### 阶段 1: 数据验证

- [ ] 确认所有传感器话题正常发布
  ```bash
  rostopic list | grep unitree_g1
  rostopic hz /unitree_g1/imu
  rostopic hz /unitree_g1/joint_states
  ```

- [ ] 验证关节名称和顺序
  ```bash
  rostopic echo /unitree_g1/joint_states -n1 | grep name
  ```

- [ ] 检查数据完整性
  ```bash
  rostopic echo /unitree_g1/joint_states -n1
  # 确认有 23 个关节的 position 和 velocity
  ```

### 阶段 2: 离线测试

- [ ] 记录真实机器人数据
  ```bash
  rosbag record /unitree_g1/imu /unitree_g1/joint_states /cmd_vel
  ```

- [ ] 回放测试 RL Policy
  ```bash
  roslaunch unitree_g1_rl unitree_g1_rl_policy.launch use_real_robot:=false
  rosbag play test.bag
  ```

- [ ] 检查输出合理性
  ```bash
  rostopic echo /unitree_g1/joint_commands
  ```

### 阶段 3: 在线测试（小心！）

- [ ] **安全措施就位**
  - [ ] 机器人悬空或有支撑
  - [ ] 急停按钮准备好
  - [ ] 限制运动范围

- [ ] 零速度测试
  ```bash
  rostopic pub /cmd_vel geometry_msgs/Twist "linear: {x: 0, y: 0, z: 0} angular: {x: 0, y: 0, z: 0}"
  ```
  期望: 机器人保持站立不动

- [ ] 低速前进测试
  ```bash
  rostopic pub /cmd_vel geometry_msgs/Twist "linear: {x: 0.2, y: 0, z: 0} angular: {x: 0, y: 0, z: 0}"
  ```
  期望: 机器人缓慢前进

- [ ] 停止测试
  ```bash
  rostopic pub /cmd_vel geometry_msgs/Twist "linear: {x: 0, y: 0, z: 0} angular: {x: 0, y: 0, z: 0}"
  ```
  期望: 机器人平稳停止

### 阶段 4: 性能验证

- [ ] 测试控制频率
  ```bash
  rostopic hz /unitree_g1/joint_commands
  # 应该稳定在 ~50 Hz
  ```

- [ ] 测试各种速度命令
  - [ ] 前进: [0.5, 0, 0]
  - [ ] 后退: [-0.5, 0, 0]
  - [ ] 左移: [0, 0.3, 0]
  - [ ] 右移: [0, -0.3, 0]
  - [ ] 旋转: [0, 0, 0.5]
  - [ ] 组合: [0.5, 0.2, 0.3]

- [ ] 记录性能指标
  - 实际速度 vs 命令速度
  - 是否有明显偏移
  - 步态是否自然

---

## 🔧 调试工具

### 查看 RL Policy 的内部状态

在 ROS Node 中添加调试发布者：

```python
# 在 UnitreeG1RLPolicyNode.__init__() 中添加
self.obs_pub = rospy.Publisher('/rl_policy/observation', Float32MultiArray, queue_size=1)
self.action_pub = rospy.Publisher('/rl_policy/action', Float32MultiArray, queue_size=1)

# 在 _control_callback() 中发布
obs_msg = Float32MultiArray(data=obs.tolist())
self.obs_pub.publish(obs_msg)

action_msg = Float32MultiArray(data=action.tolist())
self.action_pub.publish(action_msg)
```

### 可视化观测和动作

```bash
# 安装 rqt_plot
sudo apt-get install ros-$ROS_DISTRO-rqt-plot

# 可视化速度命令
rqt_plot /rl_policy/observation/data[6] /rl_policy/observation/data[7] /rl_policy/observation/data[8]

# 可视化动作
rqt_plot /rl_policy/action/data[0] /rl_policy/action/data[1]
```

---

## 📞 联系方式

**RL 模型方 (我方)**:
- 负责人: _______________
- 邮箱: _______________
- 提供内容: RL Policy checkpoint, 集成代码, 技术支持

**环境/机器人方 (对方)**:
- 负责人: _______________
- 邮箱: _______________
- 提供内容: ROS接口, 机器人参数, 传感器数据

---

## 📄 相关文档

- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - 完整技术对接文档
- [ROS_INTEGRATION.md](ROS_INTEGRATION.md) - ROS 集成详细方案
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - 快速参考手册

---

**清单版本**: v1.0  
**更新日期**: 2026-06-18
