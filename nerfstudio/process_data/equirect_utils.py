import os
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
import torch
from equilib import Equi2Pers
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from nerfstudio.utils.rich_utils import ItersPerSecColumn


def generate_planar_projections_from_equirectangular(
    image_dir: Path,
    planar_image_size: Tuple[int, int],
    samples_per_im: int,
) -> Path:
    """Generate planar projections from an equirectangular image.

    Args:
        image_dir: The directory containing the equirectangular image.
        planar_image_size: The size of the planar projections [width, height].
        samples_per_im: The number of samples to take per image.
    returns:
        The path to the planar projections directory.
    """

    device = torch.device("cuda")

    fov = 120
    yaw_pitch_pairs = []
    if samples_per_im == 8:
        fov = 120
        for i in np.arange(-180, 180, 90):
            yaw_pitch_pairs.append((i, 0))
        for i in np.arange(-180, 180, 180):
            yaw_pitch_pairs.append((i, 45))
        for i in np.arange(-180, 180, 180):
            yaw_pitch_pairs.append((i, -45))
    elif samples_per_im == 14:
        fov = 110
        for i in np.arange(-180, 180, 60):
            yaw_pitch_pairs.append((i, 0))
        for i in np.arange(-180, 180, 90):
            yaw_pitch_pairs.append((i, 45))
        for i in np.arange(-180, 180, 90):
            yaw_pitch_pairs.append((i, -45))

    equi2pers = Equi2Pers(height=planar_image_size[1], width=planar_image_size[0], fov_x=fov, mode="bilinear")
    frame_dir = image_dir
    output_dir = image_dir / "planar_projections"
    output_dir.mkdir(exist_ok=True)
    num_ims = len(os.listdir(frame_dir))
    progress = Progress(
        TextColumn("[bold blue]Generating Planar Images", justify="right"),
        BarColumn(),
        TaskProgressColumn(show_speed=True),
        ItersPerSecColumn(suffix="equirect frames/s"),
        TimeRemainingColumn(elapsed_when_finished=True, compact=True),
    )

    curr_im = 0
    with progress:
        for i in progress.track(os.listdir(frame_dir), description="", total=num_ims):
            if i.lower().endswith((".jpg", ".png", ".jpeg")):
                im = np.array(cv2.imread(os.path.join(frame_dir, i)))
                im = torch.tensor(im, dtype=torch.float32, device=device)
                im = torch.permute(im, (2, 0, 1)) / 255.0
                count = 0
                for u_deg, v_deg in yaw_pitch_pairs:
                    v_rad = torch.pi * v_deg / 180.0
                    u_rad = torch.pi * u_deg / 180.0
                    pers_image = equi2pers(im, rots={"roll": 0, "pitch": v_rad, "yaw": u_rad}) * 255.0
                    pers_image = (pers_image.permute(1, 2, 0)).type(torch.uint8).to("cpu").numpy()
                    cv2.imwrite(f"{output_dir}/{i[:-4]}_{count}.jpg", pers_image)
                    count += 1
            curr_im += 1

    return output_dir
