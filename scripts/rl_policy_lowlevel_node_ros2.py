#!/usr/bin/env python3
"""
ROS2 Node: RL Policy Controller with LowLevelCmd for Unitree SDK2
订阅速度命令，运行 RL Policy，发布 LowLevelCmd 格式的关节指令
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import numpy as np
import torch
from threading import Lock
from dataclasses import asdict

# ROS2 messages
from sensor_msgs.msg import Imu, JointState

# 自定义消息 - 尝试导入，如果失败则使用 Twist
try:
    from unitree_rl_mjlab.msg import VelocityCommand
    USING_CUSTOM_VEL_MSG = True
except ImportError:
    from geometry_msgs.msg import Twist as VelocityCommand
    USING_CUSTOM_VEL_MSG = False
    print("Warning: Using geometry_msgs/Twist instead of VelocityCommand")

# RL Policy imports
import sys
import os
sys.path.append(os.path.expanduser('~/unitree_RL/unitree_rl_mjlab'))

import mjlab.tasks
import src.tasks
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg

# Unitree SDK2 messages
try:
    from unitree_go.msg import LowCmd, MotorCmd
    USING_UNITREE_MSGS = True
except ImportError:
    try:
        from unitree_legged_msgs.msg import LowCmd, MotorCmd
        USING_UNITREE_MSGS = True
    except ImportError:
        # 如果没有 unitree 消息，使用 JointState 替代
        print("Warning: unitree messages not found, using JointState instead")
        USING_UNITREE_MSGS = False


class RLPolicyLowLevelNode(Node):
    """ROS2 node that runs RL policy and publishes LowLevelCmd"""

    def __init__(self):
        super().__init__('rl_policy_lowlevel_node')

        # 声明参数
        self.declare_parameter('checkpoint_path',
                              os.path.expanduser('~/unitree_RL/model_10000.pt'))
        self.declare_parameter('device', 'cuda:0')
        self.declare_parameter('control_rate', 50)  # Hz
        self.declare_parameter('Kp', 50.0)
        self.declare_parameter('Kd', 1.0)
        self.declare_parameter('cmd_vel_topic', '/velocity_command')
        self.declare_parameter('imu_topic', '/trunk_imu')
        self.declare_parameter('joint_states_topic', '/joint_states')
        self.declare_parameter('lowcmd_topic', '/lowcmd')

        # 获取参数
        self.checkpoint_path = self.get_parameter('checkpoint_path').value
        self.device = self.get_parameter('device').value
        self.control_rate = self.get_parameter('control_rate').value
        self.Kp = self.get_parameter('Kp').value
        self.Kd = self.get_parameter('Kd').value

        # 关节名称
        self.joint_names = self._get_joint_names()
        self.num_joints = len(self.joint_names)

        # 数据锁
        self.lock = Lock()

        # 状态变量
        self.cmd_vel = np.zeros(3, dtype=np.float32)  # [vx, vy, yaw_rate]
        self.imu_data = None
        self.joint_states = None
        self.last_action = np.zeros(self.num_joints, dtype=np.float32)
        self.phase = 0.0
        self.is_first_run = True

        # 默认关节位置
        self.default_joint_pos = self._get_default_joint_positions()

        # 动作缩放系数
        self.action_scale = self._get_action_scale()

        # 加载 RL policy
        self.get_logger().info(f"Loading RL policy from: {self.checkpoint_path}")
        self.policy = self._load_policy()
        self.get_logger().info(f"RL policy loaded successfully on device: {self.device}")

        # QoS 配置 (ROS2 需要)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # ROS2 订阅者
        self.cmd_vel_sub = self.create_subscription(
            VelocityCommand,
            self.get_parameter('cmd_vel_topic').value,
            self._cmd_vel_callback,
            qos_profile)

        self.imu_sub = self.create_subscription(
            Imu,
            self.get_parameter('imu_topic').value,
            self._imu_callback,
            qos_profile)

        self.joint_state_sub = self.create_subscription(
            JointState,
            self.get_parameter('joint_states_topic').value,
            self._joint_state_callback,
            qos_profile)

        # ROS2 发布者
        if USING_UNITREE_MSGS:
            self.lowcmd_pub = self.create_publisher(
                LowCmd,
                self.get_parameter('lowcmd_topic').value,
                qos_profile)
        else:
            self.joint_cmd_pub = self.create_publisher(
                JointState,
                self.get_parameter('lowcmd_topic').value,
                qos_profile)

        # ROS2 定时器
        timer_period = 1.0 / self.control_rate  # seconds
        self.control_timer = self.create_timer(timer_period, self._control_callback)

        self.get_logger().info("RL Policy LowLevel Node initialized")
        self.get_logger().info(f"  Control rate: {self.control_rate} Hz")
        self.get_logger().info(f"  Number of joints: {self.num_joints}")
        self.get_logger().info(f"  Using {'LowCmd' if USING_UNITREE_MSGS else 'JointState'} messages")

    def _load_policy(self):
        """加载训练好的 RL policy"""
        task_id = 'Unitree-G1-23Dof-Flat'
        env_cfg = load_env_cfg(task_id, play=True)
        agent_cfg = load_rl_cfg(task_id)

        # 禁用域随机化
        env_cfg.events.pop("encoder_bias", None)
        env_cfg.events.pop("base_com", None)
        env_cfg.events.pop("foot_friction", None)
        env_cfg.observations["actor"].enable_corruption = False

        # 创建环境
        env_cfg.scene.num_envs = 1
        env = ManagerBasedRlEnv(cfg=env_cfg, device=self.device)
        env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

        # 加载策略
        runner = MjlabOnPolicyRunner(env, asdict(agent_cfg), device=self.device)
        runner.load(self.checkpoint_path, load_cfg={"actor": True},
                   map_location=self.device)
        policy = runner.get_inference_policy(device=self.device)

        env.close()

        return policy

    def _get_joint_names(self):
        """获取关节名称列表（23个关节）"""
        return [
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

    def _get_default_joint_positions(self):
        """获取默认关节位置（站立姿态）"""
        return np.zeros(self.num_joints, dtype=np.float32)

    def _get_action_scale(self):
        """获取动作缩放系数"""
        scale = np.ones(self.num_joints, dtype=np.float32) * 0.25

        # 根据关节类型设置不同的缩放
        for i in [0, 2, 6, 8]:  # hip_pitch, hip_yaw
            scale[i] = 0.548
        for i in [1, 7]:  # hip_roll
            scale[i] = 0.351
        for i in [3, 9]:  # knee
            scale[i] = 0.351
        for i in [4, 5, 10, 11]:  # ankle
            scale[i] = 0.439
        scale[12] = 0.548  # waist_yaw
        for i in range(15, 23):  # arms
            scale[i] = 0.439

        return scale

    def _cmd_vel_callback(self, msg):
        """速度命令回调"""
        with self.lock:
            if USING_CUSTOM_VEL_MSG:
                self.cmd_vel[0] = np.clip(msg.vel_x, -1.0, 2.0)
                self.cmd_vel[1] = np.clip(msg.vel_y, -1.0, 1.0)
                self.cmd_vel[2] = np.clip(msg.yaw_rate, -1.0, 1.0)
            else:
                self.cmd_vel[0] = np.clip(msg.linear.x, -1.0, 2.0)
                self.cmd_vel[1] = np.clip(msg.linear.y, -1.0, 1.0)
                self.cmd_vel[2] = np.clip(msg.angular.z, -1.0, 1.0)

    def _imu_callback(self, msg):
        """IMU 数据回调"""
        with self.lock:
            self.imu_data = msg

    def _joint_state_callback(self, msg):
        """关节状态回调"""
        with self.lock:
            self.joint_states = msg

            if self.is_first_run and len(msg.position) >= self.num_joints:
                self.default_joint_pos = np.array(msg.position[:self.num_joints],
                                                  dtype=np.float32)
                self.is_first_run = False
                self.get_logger().info("Default joint positions initialized from current state")

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
            gravity_body = self._quat_rotate_inverse(
                [quat.w, quat.x, quat.y, quat.z], gravity_world)
            obs[3:6] = gravity_body

            # [6:9] 速度命令
            obs[6:9] = self.cmd_vel

            # [9:11] 步态相位
            self.phase += (1.0 / self.control_rate) / 0.6
            self.phase = self.phase % 1.0
            obs[9] = np.sin(2 * np.pi * self.phase)
            obs[10] = np.cos(2 * np.pi * self.phase)

            # [11:34] 关节位置（相对默认姿态）
            joint_pos = np.array(self.joint_states.position[:self.num_joints])
            obs[11:34] = joint_pos - self.default_joint_pos

            # [34:57] 关节速度
            obs[34:57] = np.array(self.joint_states.velocity[:self.num_joints])

            # [57:80] 上一时刻动作
            obs[57:80] = self.last_action

            return obs

    def _quat_rotate_inverse(self, quat, vec):
        """四元数逆旋转向量"""
        w, x, y, z = quat
        vx, vy, vz = vec

        ix = w * vx - y * vz + z * vy
        iy = w * vy - z * vx + x * vz
        iz = w * vz - x * vy + y * vx
        iw = x * vx + y * vy + z * vz

        return np.array([
            ix * w + iw * x + iy * z - iz * y,
            iy * w + iw * y + iz * x - ix * z,
            iz * w + iw * z + ix * y - iy * x,
        ])

    def _control_callback(self):
        """控制循环回调 (50Hz)"""
        # 构建观测
        obs = self._build_observation()
        if obs is None:
            if self.get_clock().now().nanoseconds / 1e9 > 5.0:
                self.get_logger().warn("Waiting for sensor data...", throttle_duration_sec=1.0)
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

        # 保存动作
        self.last_action = action

        # 计算目标位置
        target_positions = self.default_joint_pos + action * self.action_scale

        # 发布指令
        if USING_UNITREE_MSGS:
            self._publish_lowcmd(target_positions)
        else:
            self._publish_joint_state(target_positions)

    def _publish_lowcmd(self, target_positions):
        """发布 LowCmd 格式的指令"""
        lowcmd = LowCmd()

        # 设置每个关节的指令
        for i in range(self.num_joints):
            motor_cmd = MotorCmd()
            motor_cmd.mode = 0x0A  # 位置控制模式
            motor_cmd.q = float(target_positions[i])
            motor_cmd.dq = 0.0
            motor_cmd.kp = float(self.Kp)
            motor_cmd.kd = float(self.Kd)
            motor_cmd.tau = 0.0

            lowcmd.motor_cmd[i] = motor_cmd

        # 发布
        self.lowcmd_pub.publish(lowcmd)

    def _publish_joint_state(self, target_positions):
        """发布 JointState 格式的指令（备用）"""
        joint_cmd = JointState()
        joint_cmd.header.stamp = self.get_clock().now().to_msg()
        joint_cmd.header.frame_id = "base_link"
        joint_cmd.name = self.joint_names
        joint_cmd.position = target_positions.tolist()

        self.joint_cmd_pub.publish(joint_cmd)


def main(args=None):
    rclpy.init(args=args)

    try:
        node = RLPolicyLowLevelNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
