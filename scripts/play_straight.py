"""Script to test robot walking straight with fixed velocity command."""

import os
import sys
from dataclasses import asdict
from pathlib import Path

import torch
import tyro

from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import list_tasks, load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.tasks.velocity.mdp import UniformVelocityCommandCfg
from mjlab.utils.torch import configure_torch_backends
from mjlab.viewer import NativeMujocoViewer, ViserPlayViewer


def main(
    task_id: str = "Unitree-G1-23Dof-Flat",
    checkpoint_file: str | None = None,
    linear_velocity_x: float = 1.0,
    linear_velocity_y: float = 0.0,
    angular_velocity_z: float = 0.0,
    num_envs: int = 1,
    viewer: str = "auto",
    disable_randomization: bool = True,
):
    """Test robot with fixed velocity command.

    Args:
        task_id: Task identifier
        checkpoint_file: Path to checkpoint file
        linear_velocity_x: Forward velocity (m/s)
        linear_velocity_y: Lateral velocity (m/s)
        angular_velocity_z: Angular velocity (rad/s)
        num_envs: Number of environments
        viewer: Viewer backend ('auto', 'native', or 'viser')
        disable_randomization: Disable domain randomization for testing
    """
    configure_torch_backends()

    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Load configurations
    env_cfg = load_env_cfg(task_id, play=True)
    agent_cfg = load_rl_cfg(task_id)

    # Disable domain randomization if requested
    if disable_randomization:
        print("[INFO] Domain randomization disabled for testing")
        env_cfg.events.pop("encoder_bias", None)
        env_cfg.events.pop("base_com", None)
        env_cfg.events.pop("foot_friction", None)
        env_cfg.observations["actor"].enable_corruption = False

    # Override velocity command ranges to fixed values
    twist_cmd = env_cfg.commands["twist"]
    assert isinstance(twist_cmd, UniformVelocityCommandCfg)

    # Set narrow ranges around target velocity (effectively fixed)
    epsilon = 0.001
    twist_cmd.ranges.lin_vel_x = (linear_velocity_x - epsilon, linear_velocity_x + epsilon)
    twist_cmd.ranges.lin_vel_y = (linear_velocity_y - epsilon, linear_velocity_y + epsilon)
    twist_cmd.ranges.ang_vel_z = (angular_velocity_z - epsilon, angular_velocity_z + epsilon)

    print(f"[INFO] Fixed velocity command:")
    print(f"  - Linear X: {linear_velocity_x:.2f} m/s (forward)")
    print(f"  - Linear Y: {linear_velocity_y:.2f} m/s (lateral)")
    print(f"  - Angular Z: {angular_velocity_z:.2f} rad/s (yaw)")

    # Load checkpoint
    if checkpoint_file is None:
        raise ValueError("checkpoint_file is required")

    resume_path = Path(checkpoint_file)
    if not resume_path.exists():
        raise FileNotFoundError(f"Checkpoint file not found: {resume_path}")

    print(f"[INFO] Loading checkpoint: {resume_path.name}")

    # Set number of environments
    env_cfg.scene.num_envs = num_envs

    # Create environment
    env = ManagerBasedRlEnv(cfg=env_cfg, device=device)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # Load policy
    runner_cls = load_runner_cls(task_id) or MjlabOnPolicyRunner
    runner = runner_cls(env, asdict(agent_cfg), device=device)
    runner.load(
        str(resume_path), load_cfg={"actor": True}, strict=True, map_location=device
    )
    policy = runner.get_inference_policy(device=device)

    # Handle viewer selection
    if viewer == "auto":
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        viewer = "native" if has_display else "viser"

    print(f"[INFO] Starting {viewer} viewer...")

    if viewer == "native":
        NativeMujocoViewer(env, policy).run()
    elif viewer == "viser":
        ViserPlayViewer(env, policy).run()
    else:
        raise RuntimeError(f"Unsupported viewer backend: {viewer}")

    env.close()


if __name__ == "__main__":
    # Import tasks to populate the registry
    import mjlab.tasks  # noqa: F401
    import src.tasks

    tyro.cli(main)
