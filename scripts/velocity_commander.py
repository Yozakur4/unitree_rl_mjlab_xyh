#!/usr/bin/env python3
"""
简单的速度命令发布器
用于测试 RL Policy 节点
"""

import rospy
import sys

# 尝试导入自定义消息
try:
    from unitree_rl_mjlab.msg import VelocityCommand
    USING_CUSTOM_MSG = True
    print("使用 VelocityCommand 消息")
except ImportError:
    from geometry_msgs.msg import Twist as VelocityCommand
    USING_CUSTOM_MSG = False
    print("使用 geometry_msgs/Twist 消息")


def main():
    rospy.init_node('velocity_commander', anonymous=True)

    # 创建发布者
    if USING_CUSTOM_MSG:
        pub = rospy.Publisher('/velocity_command', VelocityCommand, queue_size=10)
        topic_name = '/velocity_command'
    else:
        pub = rospy.Publisher('/cmd_vel', VelocityCommand, queue_size=10)
        topic_name = '/cmd_vel'

    rate = rospy.Rate(10)  # 10 Hz

    print("速度命令发布器已启动")
    print(f"发布到话题: {topic_name}")
    print("\n控制说明:")
    print("  启动后会自动发布速度命令")
    print("  修改下面的速度值来测试不同运动")
    print("\n按 Ctrl+C 停止\n")

    # 测试序列
    test_sequence = [
        ("站立", 0.0, 0.0, 0.0, 5.0),
        ("前进 0.5 m/s", 0.5, 0.0, 0.0, 5.0),
        ("前进 0.8 m/s", 0.8, 0.0, 0.0, 5.0),
        ("停止", 0.0, 0.0, 0.0, 2.0),
        ("左移 0.3 m/s", 0.0, 0.3, 0.0, 5.0),
        ("停止", 0.0, 0.0, 0.0, 2.0),
        ("右移 0.3 m/s", 0.0, -0.3, 0.0, 5.0),
        ("停止", 0.0, 0.0, 0.0, 2.0),
        ("原地左转", 0.0, 0.0, 0.5, 5.0),
        ("停止", 0.0, 0.0, 0.0, 2.0),
        ("组合运动", 0.5, 0.2, 0.3, 5.0),
        ("停止", 0.0, 0.0, 0.0, 2.0),
    ]

    sequence_idx = 0
    start_time = rospy.Time.now()
    current_duration = test_sequence[0][4]

    try:
        while not rospy.is_shutdown():
            # 获取当前测试步骤
            desc, vx, vy, yaw_rate, duration = test_sequence[sequence_idx]

            # 检查是否该切换到下一步
            elapsed = (rospy.Time.now() - start_time).to_sec()
            if elapsed >= current_duration:
                sequence_idx = (sequence_idx + 1) % len(test_sequence)
                start_time = rospy.Time.now()
                desc, vx, vy, yaw_rate, current_duration = test_sequence[sequence_idx]
                print(f"\n>>> {desc}")
                print(f"    vx={vx:.2f}, vy={vy:.2f}, yaw_rate={yaw_rate:.2f}")

            # 创建并发布消息
            cmd = VelocityCommand()
            if USING_CUSTOM_MSG:
                cmd.vel_x = vx
                cmd.vel_y = vy
                cmd.yaw_rate = yaw_rate
            else:
                cmd.linear.x = vx
                cmd.linear.y = vy
                cmd.angular.z = yaw_rate

            pub.publish(cmd)
            rate.sleep()

    except rospy.ROSInterruptException:
        print("\n发布器已停止")
    except KeyboardInterrupt:
        print("\n发布停止命令...")
        # 发送停止命令
        cmd = VelocityCommand()
        if USING_CUSTOM_MSG:
            cmd.vel_x = 0.0
            cmd.vel_y = 0.0
            cmd.yaw_rate = 0.0
        else:
            cmd.linear.x = 0.0
            cmd.linear.y = 0.0
            cmd.angular.z = 0.0
        pub.publish(cmd)
        print("已发送停止命令")


if __name__ == '__main__':
    main()
