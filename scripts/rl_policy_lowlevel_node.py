#!/usr/bin/env python3
"""
ROS Node: RL Policy Controller with LowLevelCmd
订阅速度命令，运行 RL Policy，发布 LowLevelCmd 格式的关节指令
"""

import rospy
import numpy as np
import torch
from threading import Lock
from dataclasses import asdict

# ROS messages
from sensor_msgs.msg import Imu, JointState

# 自定义消息 - 尝试导入，如果失败则使用 Twist
try:
    from unitree_rl_mjlab.msg import VelocityCommand
    USING_CUSTOM_VEL_MSG = True
except ImportError:
    from geometry_msgs.msg import Twist as VelocityCommand
    USING_CUSTOM_VEL_MSG = False
    rospy.logwarn("Using geometry_msgs/Twist instead of VelocityCommand")

# RL Policy imports
import sys
import os
sys.path.append(os.path.expanduser('~/unitree_RL/unitree_rl_mjlab'))

import mjlab.tasks
import src.tasks
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg

# Unitree messages - 根据实际情况调整
try:
    from unitree_legged_msgs.msg import LowCmd, MotorCmd
    USING_UNITREE_MSGS = True
except ImportError:
    # 如果没有 unitree_legged_msgs，使用 JointState 替代
    rospy.logwarn("unitree_legged_msgs not found, using JointState instead")
    USING_UNITREE_MSGS = False


class RLPolicyLowLevelNode:
    """ROS node that runs RL policy and publishes LowLevelCmd"""

    def __init__(self):
        rospy.init_node('rl_policy_lowlevel_node', anonymous=False)

        # 参数配置
        self.checkpoint_path = rospy.get_param('~checkpoint_path',
                                               os.path.expanduser('~/unitree_RL/model_10000.pt'))
        self.device = rospy.get_param('~device', 'cuda:0')
        self.control_rate = rospy.get_param('~control_rate', 50)  # Hz
        self.use_simulation = rospy.get_param('~use_simulation', True)

        # 关节名称映射 (根据实际机器人调整)
        self.joint_names = self._get_joint_names()
        self.num_joints = len(self.joint_names)

        # 数据锁
        self.lock = Lock()

        # 状态变量
        self.cmd_vel = np.zeros(3, dtype=np.float32)  # [vx, vy, yaw_rate]
        self.imu_data = None
        self.joint_states = None
        self.last_action = np.zeros(self.num_joints, dtype=np.float32)
        self.phase = 0.0  # 步态相位
        self.is_first_run = True

        # 默认关节位置（站立姿态）- 需要根据实际机器人调整
        self.default_joint_pos = self._get_default_joint_positions()

        # 动作缩放系数
        self.action_scale = self._get_action_scale()

        # PD 参数（如果使用 LowLevelCmd）
        self.Kp = rospy.get_param('~Kp', 50.0)  # 默认 Kp
        self.Kd = rospy.get_param('~Kd', 1.0)   # 默认 Kd

        # 加载 RL policy
        rospy.loginfo("Loading RL policy from: %s", self.checkpoint_path)
        self.policy = self._load_policy()
        rospy.loginfo("RL policy loaded successfully on device: %s", self.device)

        # ROS 订阅者
        self.cmd_vel_sub = rospy.Subscriber(
            rospy.get_param('~cmd_vel_topic', '/velocity_command'),
            VelocityCommand, self._cmd_vel_callback, queue_size=1)

        self.imu_sub = rospy.Subscriber(
            rospy.get_param('~imu_topic', '/trunk_imu'),
            Imu, self._imu_callback, queue_size=1)

        self.joint_state_sub = rospy.Subscriber(
            rospy.get_param('~joint_states_topic', '/joint_states'),
            JointState, self._joint_state_callback, queue_size=1)

        # ROS 发布者
        if USING_UNITREE_MSGS:
            self.lowcmd_pub = rospy.Publisher(
                rospy.get_param('~lowcmd_topic', '/lowcmd'),
                LowCmd, queue_size=1)
        else:
            # 备用：使用 JointState
            self.joint_cmd_pub = rospy.Publisher(
                rospy.get_param('~joint_cmd_topic', '/joint_commands'),
                JointState, queue_size=1)

        # 控制定时器
        self.control_timer = rospy.Timer(
            rospy.Duration(1.0 / self.control_rate),
            self._control_callback)

        rospy.loginfo("RL Policy LowLevel Node initialized")
        rospy.loginfo("  Control rate: %d Hz", self.control_rate)
        rospy.loginfo("  Number of joints: %d", self.num_joints)
        rospy.loginfo("  Using %s messages",
                     "LowCmd" if USING_UNITREE_MSGS else "JointState")

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
        # 这些值需要根据实际机器人调整
        return np.zeros(self.num_joints, dtype=np.float32)

    def _get_action_scale(self):
        """获取动作缩放系数"""
        # 从训练配置中获取的缩放系数
        scale = np.ones(self.num_joints, dtype=np.float32) * 0.25  # 默认值

        # 根据关节类型设置不同的缩放
        # 髋关节俯仰/偏航
        for i in [0, 2, 6, 8]:  # hip_pitch, hip_yaw
            scale[i] = 0.548
        # 髋关节横滚
        for i in [1, 7]:  # hip_roll
            scale[i] = 0.351
        # 膝关节
        for i in [3, 9]:  # knee
            scale[i] = 0.351
        # 踝关节
        for i in [4, 5, 10, 11]:  # ankle
            scale[i] = 0.439
        # 腰部
        scale[12] = 0.548  # waist_yaw
        # 手臂
        for i in range(15, 23):  # arms
            scale[i] = 0.439

        return scale

    def _cmd_vel_callback(self, msg):
        """速度命令回调"""
        with self.lock:
            if USING_CUSTOM_VEL_MSG:
                # 使用自定义 VelocityCommand 消息
                self.cmd_vel[0] = np.clip(msg.vel_x, -1.0, 2.0)      # vx
                self.cmd_vel[1] = np.clip(msg.vel_y, -1.0, 1.0)      # vy
                self.cmd_vel[2] = np.clip(msg.yaw_rate, -1.0, 1.0)   # yaw_rate
            else:
                # 回退到使用 Twist 消息
                self.cmd_vel[0] = np.clip(msg.linear.x, -1.0, 2.0)   # vx
                self.cmd_vel[1] = np.clip(msg.linear.y, -1.0, 1.0)   # vy
                self.cmd_vel[2] = np.clip(msg.angular.z, -1.0, 1.0)  # yaw_rate

    def _imu_callback(self, msg):
        """IMU 数据回调"""
        with self.lock:
            self.imu_data = msg

    def _joint_state_callback(self, msg):
        """关节状态回调"""
        with self.lock:
            self.joint_states = msg

            # 第一次接收到关节状态，更新默认位置
            if self.is_first_run and len(msg.position) >= self.num_joints:
                self.default_joint_pos = np.array(msg.position[:self.num_joints],
                                                  dtype=np.float32)
                self.is_first_run = False
                rospy.loginfo("Default joint positions initialized from current state")

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
            self.phase += (1.0 / self.control_rate) / 0.6  # 0.6s 周期
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

    def _control_callback(self, event):
        """控制循环回调 (50Hz)"""
        # 构建观测
        obs = self._build_observation()
        if obs is None:
            if rospy.get_time() > 5.0:  # 启动5秒后才警告
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
            motor_cmd.q = target_positions[i]  # 目标位置
            motor_cmd.dq = 0.0                 # 目标速度
            motor_cmd.Kp = self.Kp             # 比例增益
            motor_cmd.Kd = self.Kd             # 微分增益
            motor_cmd.tau = 0.0                # 前馈力矩

            lowcmd.motorCmd[i] = motor_cmd

        # 发布
        self.lowcmd_pub.publish(lowcmd)

    def _publish_joint_state(self, target_positions):
        """发布 JointState 格式的指令（备用）"""
        joint_cmd = JointState()
        joint_cmd.header.stamp = rospy.Time.now()
        joint_cmd.header.frame_id = "base_link"
        joint_cmd.name = self.joint_names
        joint_cmd.position = target_positions.tolist()

        self.joint_cmd_pub.publish(joint_cmd)

    def run(self):
        """运行节点"""
        rospy.spin()


def main():
    try:
        node = RLPolicyLowLevelNode()
        node.run()
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        rospy.logerr("RL Policy Node error: %s", str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
