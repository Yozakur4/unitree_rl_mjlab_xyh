"""Diagnose straight walking performance."""

import torch
import tyro
from pathlib import Path
from dataclasses import asdict
import numpy as np

from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.tasks.velocity.mdp import UniformVelocityCommandCfg
from mjlab.utils.torch import configure_torch_backends


def main(
    task_id: str = "Unitree-G1-23Dof-Flat",
    checkpoint_file: str | None = None,
    linear_velocity_x: float = 0.8,
    num_steps: int = 1000,
    disable_randomization: bool = True,
):
    """Diagnose straight walking performance.

    Args:
        task_id: Task identifier
        checkpoint_file: Path to checkpoint file
        linear_velocity_x: Target forward velocity (m/s)
        num_steps: Number of simulation steps to run
        disable_randomization: Whether to disable domain randomization
    """
    configure_torch_backends()
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Load configurations
    env_cfg = load_env_cfg(task_id, play=True)
    agent_cfg = load_rl_cfg(task_id)

    # Disable domain randomization for diagnosis
    if disable_randomization:
        print("[INFO] Disabling domain randomization for diagnosis...")
        env_cfg.events.pop("encoder_bias", None)
        env_cfg.events.pop("base_com", None)
        env_cfg.events.pop("foot_friction", None)

        # Disable observation noise
        env_cfg.observations["actor"].enable_corruption = False

    # Set fixed velocity command
    twist_cmd = env_cfg.commands["twist"]
    assert isinstance(twist_cmd, UniformVelocityCommandCfg)
    epsilon = 0.001
    twist_cmd.ranges.lin_vel_x = (linear_velocity_x - epsilon, linear_velocity_x + epsilon)
    twist_cmd.ranges.lin_vel_y = (-epsilon, epsilon)
    twist_cmd.ranges.ang_vel_z = (-epsilon, epsilon)

    # Single environment for diagnosis
    env_cfg.scene.num_envs = 1

    # Load checkpoint
    if checkpoint_file is None:
        raise ValueError("checkpoint_file is required")
    resume_path = Path(checkpoint_file)
    if not resume_path.exists():
        raise FileNotFoundError(f"Checkpoint file not found: {resume_path}")

    print(f"[INFO] Loading checkpoint: {resume_path.name}")

    # Create environment
    env = ManagerBasedRlEnv(cfg=env_cfg, device=device)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # Load policy
    runner_cls = load_runner_cls(task_id)
    if runner_cls is None:
        from mjlab.rl import MjlabOnPolicyRunner
        runner_cls = MjlabOnPolicyRunner

    runner = runner_cls(env, asdict(agent_cfg), device=device)
    runner.load(str(resume_path), load_cfg={"actor": True}, strict=True, map_location=device)
    policy = runner.get_inference_policy(device=device)

    # Run simulation and collect data
    print(f"\n[INFO] Running {num_steps} steps with target velocity: {linear_velocity_x:.2f} m/s")
    print("[INFO] Recording trajectory data...\n")

    obs, _ = env.reset()

    positions = []
    orientations = []
    velocities = []
    commands = []

    for step in range(num_steps):
        with torch.inference_mode():
            actions = policy(obs)
        obs, _, _, _, info = env.step(actions)

        # Get robot state
        robot = env.unwrapped.scene["robot"]
        pos = robot.data.root_link_pos_w[0].cpu().numpy()
        quat = robot.data.root_link_quat_w[0].cpu().numpy()
        vel_b = robot.data.root_link_lin_vel_b[0].cpu().numpy()
        ang_vel_b = robot.data.root_link_ang_vel_b[0].cpu().numpy()

        # Get command
        cmd_mgr = env.unwrapped.command_manager
        cmd = cmd_mgr.get_command("twist")[0].cpu().numpy()

        positions.append(pos)
        orientations.append(quat)
        velocities.append(np.concatenate([vel_b, ang_vel_b]))
        commands.append(cmd)

    positions = np.array(positions)
    velocities = np.array(velocities)
    commands = np.array(commands)

    # Compute heading (yaw angle)
    def quat_to_yaw(quat):
        """Convert quaternion to yaw angle."""
        w, x, y, z = quat
        return np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))

    yaws = np.array([quat_to_yaw(q) for q in orientations])

    # Analysis
    print("="*60)
    print("STRAIGHT WALKING DIAGNOSIS")
    print("="*60)

    # 1. Position drift
    start_pos = positions[0]
    end_pos = positions[-1]
    displacement = end_pos - start_pos
    distance = np.linalg.norm(displacement[:2])
    lateral_drift = displacement[1]  # Y-axis drift

    print(f"\n1. POSITION ANALYSIS:")
    print(f"   Total distance traveled: {distance:.3f} m")
    print(f"   Forward displacement (X): {displacement[0]:+.3f} m")
    print(f"   Lateral drift (Y): {lateral_drift:+.3f} m")
    print(f"   Lateral drift percentage: {abs(lateral_drift)/distance*100:.1f}%")

    if abs(lateral_drift) > 0.1:
        print(f"   ⚠️  ISSUE: Significant lateral drift detected!")
        if lateral_drift > 0:
            print(f"      Robot drifts to the LEFT")
        else:
            print(f"      Robot drifts to the RIGHT")
    else:
        print(f"   ✓ Lateral drift is acceptable")

    # 2. Heading drift
    yaw_start = yaws[0]
    yaw_end = yaws[-1]
    yaw_drift = np.rad2deg(yaw_end - yaw_start)

    print(f"\n2. HEADING ANALYSIS:")
    print(f"   Initial yaw: {np.rad2deg(yaw_start):+.1f}°")
    print(f"   Final yaw: {np.rad2deg(yaw_end):+.1f}°")
    print(f"   Yaw drift: {yaw_drift:+.1f}°")

    if abs(yaw_drift) > 5.0:
        print(f"   ⚠️  ISSUE: Significant heading drift detected!")
        if yaw_drift > 0:
            print(f"      Robot turns LEFT")
        else:
            print(f"      Robot turns RIGHT")
    else:
        print(f"   ✓ Heading is stable")

    # 3. Velocity tracking
    vel_x_actual = velocities[:, 0]
    vel_y_actual = velocities[:, 1]
    vel_yaw_actual = velocities[:, 5]

    cmd_x = commands[:, 0]
    cmd_y = commands[:, 1]
    cmd_yaw = commands[:, 2]

    vel_x_mean = vel_x_actual.mean()
    vel_y_mean = vel_y_actual.mean()
    vel_yaw_mean = vel_yaw_actual.mean()

    error_x = np.abs(vel_x_actual - cmd_x).mean()
    error_y = np.abs(vel_y_actual - cmd_y).mean()
    error_yaw = np.abs(vel_yaw_actual - cmd_yaw).mean()

    print(f"\n3. VELOCITY TRACKING:")
    print(f"   Target velocity (X): {cmd_x[0]:.3f} m/s")
    print(f"   Actual velocity (X): {vel_x_mean:.3f} m/s (error: {error_x:.3f})")
    print(f"   Lateral velocity (Y): {vel_y_mean:+.3f} m/s (should be ~0)")
    print(f"   Angular velocity (yaw): {vel_yaw_mean:+.3f} rad/s (should be ~0)")

    if abs(vel_y_mean) > 0.05:
        print(f"   ⚠️  ISSUE: Persistent lateral velocity detected!")
    if abs(vel_yaw_mean) > 0.05:
        print(f"   ⚠️  ISSUE: Persistent angular velocity detected!")

    # 4. Trajectory visualization (ASCII)
    print(f"\n4. TRAJECTORY (Top-Down View):")
    print(f"   Each dot represents ~{num_steps//40} steps")

    # Downsample for visualization
    sample_idx = np.linspace(0, len(positions)-1, 40, dtype=int)
    x_samples = positions[sample_idx, 0]
    y_samples = positions[sample_idx, 1]

    # Normalize to ASCII grid
    x_min, x_max = x_samples.min(), x_samples.max()
    y_min, y_max = y_samples.min(), y_samples.max()

    # Create a simple ASCII plot
    width = 60
    height = 20
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    for x, y in zip(x_samples, y_samples):
        col = int((x - x_min) / (x_max - x_min + 1e-6) * (width - 1))
        row = int((y - y_min) / (y_max - y_min + 1e-6) * (height - 1))
        row = height - 1 - row  # Flip Y axis
        if 0 <= row < height and 0 <= col < width:
            grid[row][col] = '●'

    print("   " + "─" * width)
    for row in grid:
        print("   " + "".join(row))
    print("   " + "─" * width)
    print(f"   X: {x_min:.2f}m → {x_max:.2f}m")
    print(f"   Y: {y_min:.2f}m → {y_max:.2f}m")

    # 5. Recommendations
    print(f"\n5. RECOMMENDATIONS:")

    if abs(lateral_drift) > 0.1 or abs(yaw_drift) > 5.0:
        print("   The robot shows drift. Possible causes:")
        print("   • Model training issue - may need more training or better reward tuning")
        print("   • Try disabling randomization: already disabled in this test")
        print("   • Check if training data was biased (unbalanced command distribution)")
        print("\n   To improve:")
        print("   1. Increase velocity tracking reward weight")
        print("   2. Reduce tracking error tolerance (std parameter)")
        print("   3. Add explicit penalty for lateral drift")
        print("   4. Continue training from this checkpoint")
    else:
        print("   ✓ Robot walks straight reasonably well!")
        print("   Minor drift is normal due to simulation and control limitations.")

    print("\n" + "="*60)

    env.close()


if __name__ == "__main__":
    tyro.cli(main)
