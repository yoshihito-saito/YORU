# Using Basler In YORU

## Overview

YORU can use a Basler camera through the `pypylon` backend.

The practical setup is:

1. Configure the Basler camera in pylon Viewer and save a `.pfs` file if needed.
2. Set the same camera geometry in `config/yoru_pypylon_test.yaml`.
3. Launch the realtime GUI with the Basler config.
4. If needed, select and apply a `.pfs` file from the GUI.

At the moment, YORU does not treat the `.pfs` as the only source of truth.  
After loading the `.pfs`, YORU still tries to apply `camera_width`, `camera_height`, and `camera_fps` from YAML.  
Because of that, the safest workflow is to keep `.pfs` and YAML aligned.

## Launch

Use either of these:

```powershell
python -m yoru.realtime_yoru_GUI --config config/yoru_basler.yaml
```

or on Windows:

```powershell
.\run_gui_pypylon.bat
```

## Recommended Basler Config

Example:

```yaml
hardware:
  use_camera: True
  camera_backend: pypylon
  camera_serial: ""
  camera_pfs_path: ""
  camera_id: 0
  camera_width: 680
  camera_height: 480
  camera_scale: 1
  camera_fps: 40
  camera_imshow: True
```

## Meaning Of Each Setting

`camera_backend`

- Use `pypylon` for Basler cameras.

`camera_serial`

- Leave blank to select the camera by `camera_id`.
- Set a serial number if you want to lock to one specific Basler camera.

`camera_pfs_path`

- Optional path to a `.pfs` file exported from pylon Viewer.
- You can also leave it blank in YAML and choose the file later from the GUI.

`camera_id`

- Camera index used when `camera_serial` is blank.

`camera_width`, `camera_height`

- These are important in the current implementation.
- They are used for:
  - Basler width/height setting attempts
  - frame buffer initialization
  - GUI image sizing
  - recording size
  - YORU-side resize target
- Do not omit them.

`camera_scale`

- YORU always resizes frames to:
  - `camera_width * camera_scale`
  - `camera_height * camera_scale`
- If you do not want YORU to downsize the image, use `camera_scale: 1`.

`camera_fps`

- YORU tries to set the Basler frame rate from this value.
- Keep it aligned with the intended camera rate in `.pfs`.

## Best Practice For `.pfs` And YAML

Recommended workflow:

1. Decide the actual Basler ROI / width / height / fps in pylon Viewer.
2. Save that as a `.pfs` file if needed.
3. Write the same width, height, and fps in YAML.
4. Use `camera_scale: 1` unless you intentionally want a smaller processing image.

This is recommended because the current code loads `.pfs` first, then still applies YAML-side width, height, and fps.

## GUI Support For `.pfs`

When using the `pypylon` backend, the GUI shows Basler-only controls:

- current `.pfs` path
- `Select .pfs`
- `Apply .pfs`
- status text

You can start with `camera_pfs_path: ""` and choose the `.pfs` interactively.

## Recording Notes

When recording is enabled, YORU saves the processed camera frame stream used by the realtime pipeline.

Important points:

- The saved video is based on frames retrieved from Basler.
- The saved frame is the YORU processing frame after resize.
- If `camera_scale: 1` and YAML width/height match the Basler output, then the saved image is effectively the same size as the acquired image.

## About Frame Drops

The biggest risk is dropped frames.

Current Basler grabbing uses `GrabStrategy_LatestImageOnly`, so if the software cannot keep up, older frames may be skipped.

For many realtime experiments, a practical check is:

- exposure TTL count during the recording
- saved frame count in the video

If those match for the same recording period, that is usually a good sign that frame drops did not occur.

