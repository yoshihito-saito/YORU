# Using Basler In YORU

## Overview

YORU can use a Basler camera through the `pypylon` backend.

The current workflow is:

1. Configure the camera in pylon Viewer.
2. Save a `.pfs` file if you want YORU to reuse those Basler settings.
3. Put the `.pfs` path in `config/yoru_basler.yaml`.
4. Launch YORU with the Basler config.
5. Use `Start Preview` to display the camera.
6. Use `Start Recording` to display and record at the same time.

For the normal Basler path, width and height do not need to be duplicated in YAML anymore.  
If `camera_width` and `camera_height` are omitted, YORU reads `Width` and `Height` from the `.pfs` file at startup and uses those values as the recording size.

## Launch

Use:

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
  camera_pfs_path: "./test_camera/Camera_setting_40Hz.pfs"
  camera_id: 0
  camera_scale: 2
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
- If the file contains `Width` and `Height`, YORU can use those as the startup recording size.

`camera_id`

- Camera index used when `camera_serial` is blank.

`camera_scale`

- Controls the downscale factor for the live YORU processing frame.
- Saved video stays at the full recording size.
- Example:
  - `.pfs` width/height `1280x1024`
  - `camera_scale: 2`
  - YORU live frame becomes `640x512`
  - saved video remains `1280x1024`

`camera_fps`

- YORU tries to set the Basler frame rate from this value.
- Keep it aligned with the intended camera rate in the `.pfs`.

`camera_imshow`

- Controls whether the separate OpenCV window is used.
- The main Dear PyGui image window is controlled by the preview/record buttons.

## Width / Height Rules

Default Basler behavior:

- If `camera_width` and `camera_height` are omitted, YORU uses the `.pfs` width and height.
- If `camera_width` and `camera_height` are explicitly present in YAML, YORU treats those as an override and tries to apply them to the camera.

So the cleanest Basler setup is usually:

1. Set ROI / width / height in pylon Viewer.
2. Save the `.pfs`.
3. Omit `camera_width` and `camera_height` from the YAML.

## GUI Controls

The realtime GUI now separates preview from recording:

- `Start Preview`
  - starts live camera display in the GUI
  - does not record
- `Start Recording`
  - starts saving video
  - also forces the camera display on while recording is active

When recording stops, preview returns to whatever state it had before recording started.

## GUI Support For `.pfs`

When using the `pypylon` backend, the GUI shows Basler-only controls:

- current `.pfs` path
- `Select .pfs`
- `Apply .pfs`
- status text

You can start with `camera_pfs_path: ""` and choose the `.pfs` interactively.

One limitation still exists:

- if you load a new `.pfs` at runtime that changes width or height after the GUI is already open, the GUI textures are not fully rebuilt on the fly
- for geometry changes, restart YORU after switching to a different-size `.pfs`

## Recording Notes

Recording and live processing are now separated:

- saved video uses the full recording frame
- YORU live processing uses the downscaled frame from `camera_scale`

This is useful when you want:

- high-resolution saved video for later analysis
- lower-resolution live inference for stable realtime performance

## About Frame Drops

Basler grabbing currently uses `GrabStrategy_LatestImageOnly`, so if the software cannot keep up, older frames may be skipped and YORU will use the newest available frame.

For practical validation:

1. verify the Basler acquisition rate printed at startup
2. inspect the saved `*_log.csv`
3. compare frame count and duration against the expected camera rate

That gives a more reliable check than looking only at the software loop FPS inside the GUI.
