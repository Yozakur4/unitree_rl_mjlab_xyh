"""Quick visual test for straight walking."""

import sys
import time
from pathlib import Path

import torch
import tyro
from dataclasses import asdict

from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.tasks.velocity.mdp import UniformVelocityCommandCfg
from mjlab.utils.torch import configure_torch_backends


def main(
    checkpoint_file: str,
    velocity: float = 0.8,
    duration: float = 10.0,
    clean: bool = True,
):
    """Quick test to measure drift.

    Args:
        checkpoint_file: Path to checkpoint
        velocity: Forward velocity (m/s)
        duration: Test duration (seconds)
        clean: Disable randomization if True
    """
    configure_torch_backends()
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    task_id = "Unitree-G1-23Dof-Flat"
    env_cfg = load_env_cfg(task_id, play=True)
    agent_cfg = load_rl_cfg(task_id)

    if clean:
        print("[INFO] Clean test mode (no randomization)")
        env_cfg.events.pop("encoder_bias", None)
        env_cfg.events.pop("base_com", None)
        env_cfg.events.pop("foot_friction", None)
        env_cfg.observations["actor"].enable_corruption = False

    # Fixed command
    twist_cmd = env_cfg.commands["twist"]
    assert isinstance(twist_cmd, UniformVelocityCommandCfg)
    eps = 0.001
    twist_cmd.ranges.lin_vel_x = (velocity - eps, velocity + eps)
    twist_cmd.ranges.lin_vel_y = (-eps, eps)
    twist_cmd.ranges.ang_vel_z = (-eps, eps)

    env_cfg.scene.num_envs = 1

    # Load
    resume_path = Path(checkpoint_file)
    if not resume_path.exists():
        print(f"ERROR: Checkpoint not found: {resume_path}")
        sys.exit(1)

    print(f"[INFO] Loading checkpoint: {resume_path.name}")

    env = ManagerBasedRlEnv(cfg=env_cfg, device=device)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    runner_cls = load_runner_cls(task_id)
    if runner_cls is None:
        runner_cls = MjlabOnPolicyRunner

    runner = runner_cls(env, asdict(agent_cfg), device=device)
    runner.load(str(resume_path), load_cfg={"actor": True}, strict=True, map_location=device)
    policy = runner.get_inference_policy(device=device)

    # Run test
    print(f"\n{'='*60}")
    print(f"DRIFT TEST: {duration}s @ {velocity} m/s")
    print(f"{'='*60}\n")

    obs, _ = env.reset()
    robot = env.unwrapped.scene["robot"]

    start_pos = robot.data.root_link_pos_w[0].cpu().numpy().copy()
    start_time = time.time()

    steps = int(duration / env.unwrapped.step_dt)

    print("Running simulation...", end="", flush=True)

    for i in range(steps):
        with torch.inference_mode():
            actions = policy(obs)
        obs, _, _, _, _ = env.step(actions)

        if i % 100 == 0:
            print(".", end="", flush=True)

    print(" Done!\n")

    end_pos = robot.data.root_link_pos_w[0].cpu().numpy()

    # Results
    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    distance = (dx**2 + dy**2)**0.5

    print(f"Results:")
    print(f"  Forward (X):  {dx:+.3f} m")
    print(f"  Lateral (Y):  {dy:+.3f} m")
    print(f"  Distance:     {distance:.3f} m")
    print(f"  Drift ratio:  {abs(dy)/distance*100:.1f}%")
    print()

    if abs(dy) < 0.3:
        print("✓ GOOD: Minimal drift")
    elif abs(dy) < 0.8:
        print("⚠ MODERATE: Noticeable drift")
        print(f"  Direction: {'LEFT' if dy > 0 else 'RIGHT'}")
    else:
        print("✗ POOR: Significant drift")
        print(f"  Direction: {'LEFT' if dy > 0 else 'RIGHT'}")
        print("  Recommendation: Model needs improvement")

    print(f"\n{'='*60}\n")

    env.close()


if __name__ == "__main__":
    tyro.cli(main)
