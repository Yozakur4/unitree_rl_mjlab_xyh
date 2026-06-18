# PD 控制说明文档

## ❓ 常见疑问：模型输出是什么？

### 明确回答

```
输入: 观测向量 (80维) 
      ↓ 包含速度命令 (vx, vy, wz)
      
RL Policy 输出: 关节位置偏移 (23维)
                ✓ 是位置 (Position)
                ✗ 不是力矩 (Torque)
                
实际控制量: 关节目标位置 (rad)
```

---

## 🔄 完整控制流程

```
1. 用户/上层系统
   ↓ 发送速度命令
   
2. 速度命令 (vx, vy, wz)
   ↓ 与传感器数据组合
   
3. 观测向量 (80维)
   • [0:3]   机身角速度
   • [3:6]   投影重力
   • [6:9]   速度命令 ← (vx, vy, wz)
   • [9:11]  步态相位
   • [11:34] 关节位置 (23)
   • [34:57] 关节速度 (23)
   • [57:80] 上一动作 (23)
   ↓
   
4. RL Policy (神经网络)
   ↓ 推理 < 1ms
   
5. 动作向量 (23维)
   • action[i] ∈ [-1, 1] (归一化)
   • 表示：相对默认姿态的位置偏移
   ↓
   
6. 缩放和偏移
   target_pos[i] = default_pos[i] + action[i] * scale[i]
   ↓
   
7. 关节位置指令 (23维, 单位: rad)
   ↓ 发送给执行器
   
8. 【PD 控制器】← 这里！
   在仿真: MuJoCo 执行器模型
   在真机: Unitree SDK 伺服控制器
   ↓ 计算所需力矩
   
9. 力矩指令 (23维, 单位: Nm)
   τ[i] = Kp * (target_pos[i] - current_pos[i]) 
        + Kd * (0 - current_vel[i])
   ↓
   
10. 电机执行
    实际输出力矩
```

---

## 📍 PD 控制在哪里？

### 在训练/仿真环境中 (MuJoCo)

**位置**: MuJoCo 物理引擎内部

**实现方式**:
- MuJoCo 的执行器模型 (actuator model)
- 定义在 MJCF XML 文件中
- 文件: `src/assets/robots/unitree_g1/xmls/g1_23dof.xml`

**MuJoCo 执行器类型**:
```xml
<!-- MuJoCo 会自动为 joint 创建位置伺服 -->
<joint name="left_hip_pitch_joint" range="-2.5307 2.8798"/>

<!-- MuJoCo 内部实现 PD 控制: -->
<!-- τ = Kp * (target - current) - Kd * velocity -->
```

**PD 参数**:
- MuJoCo 根据关节特性自动调整
- 或在 XML 中通过 `<general>` 执行器显式定义
- 对于 G1-23DOF，使用的是隐式位置控制

### 在真实机器人上 (Unitree G1)

**位置**: 机器人底层控制器 (MCU/伺服驱动器)

**实现方式**:
- Unitree SDK 的伺服控制系统
- 每个关节独立的 PD 控制器
- 运行在关节驱动器的嵌入式控制器中

**控制接口**:
```python
# 通过 Unitree SDK 发送位置指令
motor_cmd.q = target_position    # 目标位置 (rad)
motor_cmd.dq = 0                  # 目标速度 (通常为0)
motor_cmd.Kp = Kp_value           # 比例增益
motor_cmd.Kd = Kd_value           # 微分增益
motor_cmd.tau_ff = 0              # 前馈力矩 (可选)
```

**PD 参数来源**:
- Unitree 出厂默认参数
- 可通过 SDK 调整
- 需要机器人制造商提供推荐值

---

## 🔧 各环节的责任划分

### RL Policy 的责任

```python
✓ 接收: 观测 (传感器数据 + 命令)
✓ 输出: 关节位置偏移 (归一化 [-1,1])
✗ 不管: 如何转换为力矩
✗ 不管: PD 参数是什么
```

### 位置控制器 (PD) 的责任

```python
✓ 接收: 目标位置 + 当前位置/速度
✓ 计算: 所需力矩
✓ 输出: 力矩指令给电机
✗ 不管: 目标位置从哪来
```

### 你的集成代码的责任

```python
✓ 获取传感器数据
✓ 构建观测向量
✓ 调用 RL Policy
✓ 缩放动作 → 目标位置
✓ 发送位置指令给机器人
✗ 不管: 力矩如何计算 (由底层完成)
```

---

## 🎯 对 ROS 集成的影响

### ROS 消息类型

```python
# 发布的是位置指令，不是力矩
joint_cmd = JointState()
joint_cmd.position = target_positions  # ✓ 使用这个
joint_cmd.velocity = []                # 通常为空
joint_cmd.effort = []                  # ✗ 不用这个 (力矩)
```

### Unitree SDK 接口示例

```python
# 如果使用 Unitree SDK (不是标准 ROS)
for i in range(23):
    motor_cmd[i].mode = MotorMode.POS_MODE  # 位置控制模式
    motor_cmd[i].q = target_positions[i]    # 目标位置
    motor_cmd[i].dq = 0                     # 目标速度 = 0
    motor_cmd[i].Kp = Kp_values[i]          # 需要从环境方获取
    motor_cmd[i].Kd = Kd_values[i]          # 需要从环境方获取
    motor_cmd[i].tau = 0                    # 前馈力矩 = 0
```

---

## 📋 需要向环境方确认的 PD 参数

### 真实机器人部署时必须确认：

```yaml
1. 控制模式:
   [ ] 位置控制 (Position Control) ← 最可能
   [ ] 速度控制 (Velocity Control)
   [ ] 力矩控制 (Torque Control)
   [ ] 混合模式

2. 如果是位置控制，需要 PD 参数:
   
   每个关节的 Kp (比例增益):
   - left_hip_pitch: _____
   - left_hip_roll: _____
   - ... (23个关节)
   
   每个关节的 Kd (微分增益):
   - left_hip_pitch: _____
   - left_hip_roll: _____
   - ... (23个关节)

3. 是否可以使用默认 PD 参数:
   [ ] 是 - SDK 有默认值
   [ ] 否 - 需要显式设置

4. 位置指令的发送接口:
   [ ] 标准 ROS JointState
   [ ] Unitree SDK 专有接口
   [ ] 其他: _____________
```

---

## 💡 关键理解

### 为什么 RL Policy 输出位置而不是力矩？

1. **简化训练**：位置控制更稳定，易于学习
2. **硬件抽象**：不同电机的力矩特性不同，位置更通用
3. **安全性**：位置限位比力矩限位更容易实现
4. **实用性**：大多数机器人使用位置控制模式

### PD 控制为什么在底层？

1. **实时性**：PD 控制需要高频率 (> 1kHz)
2. **硬件加速**：在电机驱动器上直接实现
3. **稳定性**：与硬件特性紧密相关
4. **标准化**：几乎所有伺服系统都内置 PD 控制

---

## 🔗 相关文档

- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - 完整技术规格
- [ROS_INTEGRATION.md](ROS_INTEGRATION.md) - ROS 接口实现
- [ROS_CHECKLIST.md](ROS_CHECKLIST.md) - 对接清单（需添加 PD 参数）

---

**文档版本**: v1.0  
**最后更新**: 2026-06-18
