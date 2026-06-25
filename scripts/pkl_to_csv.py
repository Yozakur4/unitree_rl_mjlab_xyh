"""Convert motion pickle files to the CSV format consumed by csv_to_npz.py."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Literal

import numpy as np
import tyro


DOF_COUNTS = {
    "g1": 29,
    "g1_23dof": 23,
}


def _load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def _iter_motions(obj, fallback_name: str):
    if isinstance(obj, dict):
        if {"root_trans_offset", "root_rot", "dof"}.issubset(obj.keys()):
            yield fallback_name, obj
            return
        for key, value in obj.items():
            name = Path(str(key)).stem or fallback_name
            if isinstance(value, dict) and {"root_trans_offset", "root_rot", "dof"}.issubset(
                value.keys()
            ):
                yield name, value
            else:
                raise ValueError(f"Unsupported nested pickle entry for key: {key}")
        return
    raise ValueError(f"Unsupported pickle root type: {type(obj)!r}")


def _quat_to_xyzw(quat: np.ndarray, quat_order: Literal["xyzw", "wxyz"]) -> np.ndarray:
    quat = np.asarray(quat, dtype=np.float32)
    if quat_order == "wxyz":
        quat = quat[:, [1, 2, 3, 0]]
    norm = np.linalg.norm(quat, axis=1, keepdims=True)
    norm = np.where(norm > 1.0e-8, norm, 1.0)
    return quat / norm


def main(
    input_file: str,
    output_dir: str | None = None,
    output_name: str | None = None,
    robot: Literal["g1", "g1_23dof"] = "g1_23dof",
    quat_order: Literal["xyzw", "wxyz"] = "xyzw",
    root_z_offset: float = 0.0,
) -> None:
    """Convert a motion pkl to one or more no-header CSV motion files.

    The output CSV columns are:
    root xyz, root quaternion xyzw, joint positions.
    """
    input_path = Path(input_file).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    if output_dir is None:
        output_root = input_path.parent.parent
    else:
        output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    expected_dof = DOF_COUNTS[robot]
    obj = _load_pickle(input_path)

    outputs: list[Path] = []
    for motion_name, motion in _iter_motions(obj, input_path.stem):
        root_pos = np.asarray(motion["root_trans_offset"], dtype=np.float32)
        root_quat = _quat_to_xyzw(np.asarray(motion["root_rot"], dtype=np.float32), quat_order)
        dof = np.asarray(motion["dof"], dtype=np.float32)

        if root_pos.ndim != 2 or root_pos.shape[1] != 3:
            raise ValueError(f"{motion_name}: root_trans_offset must have shape [T, 3]")
        if root_quat.ndim != 2 or root_quat.shape[1] != 4:
            raise ValueError(f"{motion_name}: root_rot must have shape [T, 4]")
        if dof.ndim != 2 or dof.shape[1] != expected_dof:
            raise ValueError(
                f"{motion_name}: expected {expected_dof} dof columns for {robot}, "
                f"got shape {dof.shape}"
            )
        if not (len(root_pos) == len(root_quat) == len(dof)):
            raise ValueError(f"{motion_name}: root/dof frame counts do not match")

        if root_z_offset:
            root_pos = root_pos.copy()
            root_pos[:, 2] += float(root_z_offset)

        data = np.concatenate([root_pos, root_quat, dof], axis=1)
        name = output_name or motion_name
        if len(list(_iter_motions(obj, input_path.stem))) > 1 and output_name:
            name = f"{Path(output_name).stem}_{motion_name}"
        output_path = output_root / f"{Path(name).stem}.csv"
        np.savetxt(output_path, data, delimiter=",", fmt="%.9f")
        outputs.append(output_path)

        fps = motion.get("fps", None)
        fps_value = int(np.asarray(fps).item()) if fps is not None else "unknown"
        print(
            f"wrote {output_path} frames={data.shape[0]} cols={data.shape[1]} "
            f"fps={fps_value}"
        )

    for output_path in outputs:
        print()
        print("next:")
        print(
            "python scripts/csv_to_npz.py "
            f"--input-file {output_path} "
            f"--output-name {output_path.stem}.npz "
            "--input-fps 30 --output-fps 50 "
            f"--robot {robot}"
        )


if __name__ == "__main__":
    tyro.cli(main)
