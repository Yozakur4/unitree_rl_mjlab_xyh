# ROS 接口集成方案

## 1. ROS 消息接口设计

### 1.1 速度命令订阅 (Twist Command)

**话题**: `/cmd_vel` 或 `/unitree_g1/cmd_vel`  
**消息类型**: `geometry_msgs/Twist`

```python
# 消息结构
geometry_msgs/Twist:
  linear:
    x: float64    # 前进速度 (m/s), 范围 [-1.0, 2.0]
    y: float64    # 横向速度 (m/s), 范围 [-1.0, 1.0]
    z: float64    # 未使用，设为 0
  angular:
    x: float64    # 未使用，设为 0
    y: float64    # 未使用，设为 0
    z: float64    # 旋转速度 (rad/s), 范围 [-1.0, 1.0]
```

**映射关系**:
```python
rl_command[0] = twist.linear.x   # lin_vel_x
rl_command[1] = twist.linear.y   # lin_vel_y
rl_command[2] = twist.angular.z  # ang_vel_z
```

### 1.2 关节指令发布 (Joint Commands)

**话题**: `/unitree_g1/joint_commands`  
**消息类型**: `sensor_msgs/JointState` 或自定义消息

```python
sensor_msgs/JointState:
  header:
    stamp: rospy.Time.now()
    frame_id: "base_link"
  name: [joint_names]          # 23个关节名称
  position: [target_positions]  # 23个目标位置 (rad)
  velocity: []                  # 可选
  effort: []                    # 可选
```

**关节顺序** (23个关节):
```python
joint_names = [
    # 左腿 (0-5)
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    
    # 右腿 (6-11)
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    
    # 腰部 (12-14)
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
    
    # 左臂 (15-18)
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    
    # 右臂 (19-22)
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
]
```

### 1.3 机器人状态订阅 (用于构建观测)

需要订阅以下话题来构建完整的观测向量：

#### a) IMU 数据
**话题**: `/unitree_g1/imu`  
**消息类型**: `sensor_msgs/Imu`
```python
# 需要的字段
imu.angular_velocity.x  # 角速度 x
imu.angular_velocity.y  # 角速度 y
imu.angular_velocity.z  # 角速度 z
imu.orientation         # 四元数，用于计算投影重力
```

#### b) 关节状态
**话题**: `/unitree_g1/joint_states`  
**消息类型**: `sensor_msgs/JointState`
```python
# 需要的字段
joint_states.position[0:23]  # 23个关节位置
joint_states.velocity[0:23]  # 23个关节速度
```

---

## 2. ROS Node 实现方案

### 2.1 完整的 ROS Node 代码

```python
#!/usr/bin/env python3
"""
Unitree G1 RL Policy ROS Node
订阅机器人状态和速度命令，发布关节指令
"""

import rospy
import torch
import numpy as np
from dataclasses import asdict
from threading import Lock

# ROS messages
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu, JointState

# RL Policy imports
import mjlab.tasks
import src.tasks
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg


class UnitreeG1RLPolicyNode:
    """ROS node that runs RL policy for Unitree G1"""
    
    def __init__(self):
        rospy.init_node('unitree_g1_rl_policy', anonymous=False)
        
        # 参数
        self.checkpoint_path = rospy.get_param('~checkpoint_path', 
                                               '/home/user/unitree_RL/model_10000.pt')
        self.device = rospy.get_param('~device', 'cuda:0')
        self.control_rate = rospy.get_param('~control_rate', 50)  # Hz
        self.use_real_robot = rospy.get_param('~use_real_robot', False)
        
        # 数据锁
        self.lock = Lock()
        
        # 状态变量
        self.cmd_vel = np.zeros(3, dtype=np.float32)  # [vx, vy, wz]
        self.imu_data = None
        self.joint_states = None
        self.last_action = np.zeros(23, dtype=np.float32)
        self.phase = 0.0  # 步态相位
        
        # 默认关节位置（站立姿态）
        self.default_joint_pos = self._get_default_joint_positions()
        
        # 加载 RL policy
        rospy.loginfo("Loading RL policy...")
        self.policy, self.env_cfg = self._load_policy()
        rospy.loginfo("RL policy loaded successfully")
        
        # 关节名称
        self.joint_names = self._get_joint_names()
        
        # ROS 订阅者
        self.cmd_vel_sub = rospy.Subscriber(
            '/cmd_vel', Twist, self._cmd_vel_callback, queue_size=1)
        self.imu_sub = rospy.Subscriber(
            '/unitree_g1/imu', Imu, self._imu_callback, queue_size=1)
        self.joint_state_sub = rospy.Subscriber(
            '/unitree_g1/joint_states', JointState, self._joint_state_callback, queue_size=1)
        
        # ROS 发布者
        self.joint_cmd_pub = rospy.Publisher(
            '/unitree_g1/joint_commands', JointState, queue_size=1)
        
        # 控制定时器
        self.control_timer = rospy.Timer(
            rospy.Duration(1.0 / self.control_rate), self._control_callback)
        
        rospy.loginfo("Unitree G1 RL Policy Node initialized")
    
    def _load_policy(self):
        """加载训练好的 RL policy"""
        task_id = 'Unitree-G1-23Dof-Flat'
        env_cfg = load_env_cfg(task_id, play=True)
        agent_cfg = load_rl_cfg(task_id)
        
        # 禁用域随机化（真机部署）
        if self.use_real_robot:
            env_cfg.events.pop("encoder_bias", None)
            env_cfg.events.pop("base_com", None)
            env_cfg.events.pop("foot_friction", None)
            env_cfg.observations["actor"].enable_corruption = False
        
        # 创建环境（仅用于加载策略）
        env_cfg.scene.num_envs = 1
        env = ManagerBasedRlEnv(cfg=env_cfg, device=self.device)
        env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
        
        # 加载策略
        runner = MjlabOnPolicyRunner(env, asdict(agent_cfg), device=self.device)
        runner.load(self.checkpoint_path, load_cfg={"actor": True}, 
                   map_location=self.device)
        policy = runner.get_inference_policy(device=self.device)
        
        env.close()
        
        return policy, env_cfg
    
    def _get_joint_names(self):
        """获取关节名称列表"""
        return [
            # 左腿
            "left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint",
            "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint",
            # 右腿
            "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint",
            "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint",
            # 腰部
            "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint",
            # 左臂
            "left_shoulder_pitch_joint", "left_shoulder_roll_joint",
            "left_shoulder_yaw_joint", "left_elbow_joint",
            # 右臂
            "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
            "right_shoulder_yaw_joint", "right_elbow_joint",
        ]
    
    def _get_default_joint_positions(self):
        """获取默认关节位置（站立姿态）"""
        # 这些值需要根据实际机器人调整
        return np.zeros(23, dtype=np.float32)
    
    def _cmd_vel_callback(self, msg):
        """速度命令回调"""
        with self.lock:
            self.cmd_vel[0] = np.clip(msg.linear.x, -1.0, 2.0)   # vx
            self.cmd_vel[1] = np.clip(msg.linear.y, -1.0, 1.0)   # vy
            self.cmd_vel[2] = np.clip(msg.angular.z, -1.0, 1.0)  # wz
    
    def _imu_callback(self, msg):
        """IMU 数据回调"""
        with self.lock:
            self.imu_data = msg
    
    def _joint_state_callback(self, msg):
        """关节状态回调"""
        with self.lock:
            self.joint_states = msg
    
    def _build_observation(self):
        """构建 RL policy 的观测向量 (80维)"""
        with self.lock:
            if self.imu_data is None or self.joint_states is None:
                return None
            
            obs = np.zeros(80, dtype=np.float32)
            
            # [0:3] 机身角速度
            obs[0] = self.imu_data.angular_velocity.x
            obs[1] = self.imu_data.angular_velocity.y
            obs[2] = self.imu_data.angular_velocity.z
            
            # [3:6] 投影重力
            quat = self.imu_data.orientation
            gravity_world = np.array([0, 0, -1.0])
            # 将重力转换到机身坐标系
            gravity_body = self._quat_rotate_inverse(
                [quat.w, quat.x, quat.y, quat.z], gravity_world)
            obs[3:6] = gravity_body
            
            # [6:9] 速度命令
            obs[6:9] = self.cmd_vel
            
            # [9:11] 步态相位
            self.phase += (1.0 / self.control_rate) / 0.6  # 0.6s 周期
            self.phase = self.phase % 1.0
            obs[9] = np.sin(2 * np.pi * self.phase)
            obs[10] = np.cos(2 * np.pi * self.phase)
            
            # [11:34] 关节位置（相对默认姿态）
            joint_pos = np.array(self.joint_states.position[:23])
            obs[11:34] = joint_pos - self.default_joint_pos
            
            # [34:57] 关节速度
            obs[34:57] = np.array(self.joint_states.velocity[:23])
            
            # [57:80] 上一时刻动作
            obs[57:80] = self.last_action
            
            return obs
    
    def _quat_rotate_inverse(self, quat, vec):
        """四元数逆旋转向量"""
        w, x, y, z = quat
        vx, vy, vz = vec
        
        # q^-1 * v * q
        ix = w * vx - y * vz + z * vy
        iy = w * vy - z * vx + x * vz
        iz = w * vz - x * vy + y * vx
        iw = x * vx + y * vy + z * vz
        
        return np.array([
            ix * w + iw * x + iy * z - iz * y,
            iy * w + iw * y + iz * x - ix * z,
            iz * w + iw * z + ix * y - iy * x,
        ])
    
    def _control_callback(self, event):
        """控制循环回调 (50Hz)"""
        # 构建观测
        obs = self._build_observation()
        if obs is None:
            rospy.logwarn_throttle(1.0, "Waiting for sensor data...")
            return
        
        # 转换为 torch tensor
        obs_tensor = torch.from_numpy(obs).unsqueeze(0).to(self.device)
        
        # 运行策略
        with torch.inference_mode():
            action_tensor = self.policy(obs_tensor)
        
        # 转换回 numpy
        action = action_tensor.squeeze(0).cpu().numpy()
        
        # 裁剪动作
        action = np.clip(action, -1.0, 1.0)
        
        # 保存动作用于下一次观测
        self.last_action = action
        
        # 发布关节指令
        self._publish_joint_commands(action)
    
    def _publish_joint_commands(self, action):
        """发布关节指令"""
        # 将归一化动作转换为关节目标位置
        # target_pos = default_pos + action * scale
        # scale 需要根据实际机器人调整
        action_scale = 0.25  # 示例缩放系数
        target_positions = self.default_joint_pos + action * action_scale
        
        # 创建 JointState 消息
        joint_cmd = JointState()
        joint_cmd.header.stamp = rospy.Time.now()
        joint_cmd.header.frame_id = "base_link"
        joint_cmd.name = self.joint_names
        joint_cmd.position = target_positions.tolist()
        
        # 发布
        self.joint_cmd_pub.publish(joint_cmd)
    
    def run(self):
        """运行节点"""
        rospy.spin()


if __name__ == '__main__':
    try:
        node = UnitreeG1RLPolicyNode()
        node.run()
    except rospy.ROSInterruptException:
        pass
```

---

## 3. ROS Launch 文件

```xml
<!-- unitree_g1_rl_policy.launch -->
<launch>
  <!-- RL Policy 参数 -->
  <arg name="checkpoint_path" default="$(env HOME)/unitree_RL/model_10000.pt" />
  <arg name="device" default="cuda:0" />
  <arg name="control_rate" default="50" />
  <arg name="use_real_robot" default="true" />
  
  <!-- 启动 RL Policy Node -->
  <node name="unitree_g1_rl_policy" pkg="unitree_g1_rl" type="rl_policy_node.py" output="screen">
    <param name="checkpoint_path" value="$(arg checkpoint_path)" />
    <param name="device" value="$(arg device)" />
    <param name="control_rate" value="$(arg control_rate)" />
    <param name="use_real_robot" value="$(arg use_real_robot)" />
  </node>
  
  <!-- 可选：启动速度命令源 -->
  <!-- 例如 teleop_twist_keyboard -->
  <node name="teleop_keyboard" pkg="teleop_twist_keyboard" type="teleop_twist_keyboard.py" output="screen">
    <remap from="cmd_vel" to="/cmd_vel" />
  </node>
  
</launch>
```

---

## 4. 使用方法

### 4.1 安装依赖
```bash
# 在 ROS workspace
cd ~/catkin_ws/src
git clone <your_package>
cd ~/catkin_ws
catkin_make

# 确保 Python 环境有 RL 依赖
conda activate unitree_rl_mjlab
pip install rospkg
```

### 4.2 启动节点
```bash
# 方法1: 使用 launch 文件
roslaunch unitree_g1_rl unitree_g1_rl_policy.launch

# 方法2: 直接运行节点
conda activate unitree_rl_mjlab
rosrun unitree_g1_rl rl_policy_node.py \
  _checkpoint_path:=/home/user/unitree_RL/model_10000.pt \
  _device:=cuda:0 \
  _use_real_robot:=true
```

### 4.3 发送速度命令测试
```bash
# 方法1: 使用 rostopic pub
rostopic pub /cmd_vel geometry_msgs/Twist \
  "linear:
    x: 0.8
    y: 0.0
    z: 0.0
  angular:
    x: 0.0
    y: 0.0
    z: 0.0"

# 方法2: 使用键盘控制
rosrun teleop_twist_keyboard teleop_twist_keyboard.py
```

---

## 5. 话题监控

### 查看话题列表
```bash
rostopic list
```

### 监控速度命令
```bash
rostopic echo /cmd_vel
```

### 监控关节指令
```bash
rostopic echo /unitree_g1/joint_commands
```

### 检查话题频率
```bash
rostopic hz /unitree_g1/joint_commands
# 应该输出 ~50 Hz
```

---

## 6. 关键注意事项

### 6.1 坐标系对齐
- **ROS 标准**: X前 Y左 Z上 (REP-103)
- **确保**: RL policy 和 ROS 使用相同的坐标系定义

### 6.2 关节名称映射
- **重要**: 确保 `joint_names` 与实际机器人的关节名称完全一致
- 检查方法:
```bash
rostopic echo /unitree_g1/joint_states -n1
```

### 6.3 默认关节位置
- **必须**: 根据实际机器人的站立姿态设置 `default_joint_pos`
- 获取方法: 让机器人站立，记录此时的关节位置

### 6.4 动作缩放系数
- **需要调整**: `action_scale` 需要根据实际机器人的关节范围调整
- 参考训练时的 `G1_23DOF_ACTION_SCALE`

### 6.5 安全措施
```python
# 添加到 ROS Node
# 1. 速度限制
def _cmd_vel_callback(self, msg):
    self.cmd_vel[0] = np.clip(msg.linear.x, -1.0, 2.0)
    
# 2. 关节限制
def _publish_joint_commands(self, action):
    target_positions = np.clip(target_positions, joint_lower_limits, joint_upper_limits)
    
# 3. 急停机制
if emergency_stop:
    return  # 不发布新的指令
```

---

## 7. 调试技巧

### 7.1 记录 rosbag
```bash
# 记录所有相关话题
rosbag record /cmd_vel /unitree_g1/imu /unitree_g1/joint_states /unitree_g1/joint_commands

# 回放测试
rosbag play test.bag
```

### 7.2 可视化
```bash
# 在 RViz 中可视化机器人
rosrun rviz rviz
# 添加 RobotModel 和 TF displays
```

### 7.3 性能监控
```python
import time

def _control_callback(self, event):
    start_time = time.time()
    # ... policy inference ...
    inference_time = time.time() - start_time
    
    if inference_time > 0.02:  # 50Hz -> 20ms
        rospy.logwarn(f"Inference too slow: {inference_time*1000:.1f}ms")
```

---

## 8. 与环境开发者的对接清单

### 需要环境方提供的信息：

- [ ] **ROS 话题名称**
  - IMU 数据话题
  - 关节状态话题
  - 关节指令话题
  - 速度命令话题

- [ ] **关节名称列表**（精确的 23 个关节名称）

- [ ] **默认站立姿态**（23 个关节的默认位置）

- [ ] **关节范围**
  - 每个关节的最小/最大位置限制
  - 每个关节的最大速度限制

- [ ] **动作缩放系数**（`G1_23DOF_ACTION_SCALE` 的具体值）

- [ ] **坐标系定义**
  - 机身坐标系的定义（X/Y/Z 方向）
  - IMU 坐标系是否与机身对齐

- [ ] **控制模式**
  - 位置控制 vs 速度控制
  - 是否需要力矩前馈

### 需要向环境方说明的信息：

- [ ] **控制频率**: 50 Hz
- [ ] **输入命令范围**:
  - `lin_vel_x`: [-1.0, 2.0] m/s
  - `lin_vel_y`: [-1.0, 1.0] m/s
  - `ang_vel_z`: [-1.0, 1.0] rad/s
- [ ] **输出**: 23 个关节的目标位置（相对默认姿态的偏移）
- [ ] **延迟**: 策略推理 < 1ms，总控制周期 20ms

---

**文档版本**: v1.0  
**适用于**: ROS Melodic / Noetic  
**参考**: [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
