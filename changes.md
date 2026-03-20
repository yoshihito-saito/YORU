# Changes Summary

## Basler / pypylon backend

- Added and validated the `capture_streamPylon` backend in [`yoru/libs/imager.py`](yoru/libs/imager.py).
- Confirmed the backend:
  - selects a Basler camera by index or serial
  - opens the camera with `pypylon`
  - converts grab results to NumPy arrays
  - normalizes frames to YORU's expected 3-channel BGR format
  - writes frames into `current_camera_frame` for the existing live pipeline

## Basler `.pfs` camera settings

- Added optional `.pfs` loading support via `camera_pfs_path`.
- `capture_streamPylon.startCapture()` loads the `.pfs` after opening the camera and before grabbing starts.
- Added GUI support for Basler `.pfs` selection and apply:
  - `yoru/libs/file_operation_realtime.py` includes a `.pfs` file picker
  - `yoru/realtime_yoru_GUI.py` shows Basler-only controls for:
    - current `camera_pfs_path`
    - `Select .pfs`
    - `Apply .pfs`
    - live status text
  - the running pypylon capture loop can reload `.pfs` settings on request without restarting the whole GUI
- Added shared runtime state in `yoru/libs/init_realtime.py` for:
  - `camera_pfs_reload_requested`
  - `camera_pfs_status`
  - `camera_pfs_last_loaded`
- `capture_streamPylon` reports:
  - no file selected
  - file not found
  - successful load
  - apply/restart failures

## Basler geometry / `.pfs` precedence

- Basler width and height can now come from the `.pfs` file instead of being forced from YAML.
- `yoru/libs/init_realtime.py` reads `Width` and `Height` directly from the configured `.pfs` at startup when `camera_width` and `camera_height` are omitted.
- `capture_streamPylon` only reapplies width and height from YAML when those values are explicitly configured.
- `config/yoru_basler.yaml` no longer needs `camera_width` and `camera_height` for the normal `.pfs`-driven workflow.
- `config/template.yaml`, `tests/schema/yoru_config.schema.json`, and `tests/test_config_template.py` were updated so Basler width/height are no longer treated as mandatory in that path.

## Recording / live processing split

- Recording now saves the full camera frame while YORU processes a downscaled live frame.
- `camera_scale` now controls the YORU live-processing size, while saved video keeps the full recording size.
- Recording uses a queue-backed writer so saving is decoupled from the rest of the realtime loop.
- The recorder now tries safer codecs in order:
  - `MJPG`
  - `XVID`
  - `DIVX`
  - `mp4v`
- The recorder now:
  - prints the codec selected at runtime
  - validates frame size before writing
  - closes more cleanly on stop/quit
- Recording refuses to start when no export folder is set.

## Basler preview / recording controls

- The realtime GUI now starts with the Basler camera idle.
- Added an explicit `Start Preview` button in [`yoru/realtime_yoru_GUI.py`](yoru/realtime_yoru_GUI.py):
  - preview shows the live camera image in the GUI
  - preview alone does not start recording
- Added an explicit `Start Recording` button:
  - recording saves video
  - recording also forces the live camera view on
  - when recording stops, preview returns to its prior state
- The Basler grab loop now only starts grabbing when preview or recording is active.

## Basler FPS visibility

- Added a direct Basler acquisition-rate readout in `capture_streamPylon.startCapture()`.
- YORU now attempts to read and print the camera-side rate from:
  - `ResultingFrameRate`
  - `AcquisitionFrameRate`
  - `AcquisitionFrameRateAbs`
- The value is stored in `m_dict["camera_acquisition_fps"]`.
- The GUI FPS bar now uses the camera-side acquisition rate when available instead of the variable software loop rate.
- Basler frame-rate writes also try `AcquisitionFrameRateAbs` when `AcquisitionFrameRate` is unavailable.
- Startup prints which frame-rate node accepted the requested FPS, if any.

## Trigger / Arduino changes

- Investigated both trigger modes:
  - `straight` for raw serial commands to a custom Arduino sketch
  - `standard_arduino` for Firmata-based direct pin control
- Fixed serial-only trigger handling in `yoru/libs/trigger.py` so serial plugins do not also try to open the port via the Firmata path.
- Added proper `close()` handling for serial trigger plugins so COM ports are released cleanly.
- Added terminal debug prints to `trigger_plugins/straight.py`.
- Fixed `trigger_plugins/standard_arduino.py` by removing a bad import that caused plugin initialization to crash after opening the COM port.
- Updated trigger startup cleanup in `yoru/libs/trigger.py` so a plugin-init failure closes the already-opened Firmata port instead of leaving the COM port locked.

## Realtime GUI / startup fixes

- Fixed `config/yoru_default.yaml` so it parses correctly as YAML again.
- Updated `config/yoru_pypylon_test.yaml` so the sample `.pfs` path is blank by default instead of pointing to a machine-specific local path.
- `yoru/realtime_yoru_GUI.py` supports `-c` / `--config` when launched directly.
- `run_gui_pypylon.bat`:
  - starts from the repository directory
  - passes `--config config/yoru_pypylon_test.yaml`
  - avoids relying on a hard-coded user-specific conda activation path

## Test updates

- Added and/or updated tests around the pypylon backend in `tests/test_imager_pylon.py`.
- Added CSV-based frame-rate analysis in:
  - `yoru/libs/frame_rate_analysis.py`
  - `tests/test_camera_rate_analysis.py`
- Added coverage for:
  - backend initialization
  - device selection
  - frame grabbing
  - cleanup
  - `.pfs` loading
  - async recorder frame copying
  - camera-log FPS analysis
- Fixed script-style tests so pytest reports real failures instead of treating boolean returns as success:
  - `tests/test_frame_grab.py`
  - `tests/test_camera_hardware.py`
  - `tests/test_video_recording.py`

## Important operational notes

- Hardware-trigger tests and hardware-recording tests should be run sequentially, not in parallel, because the Basler camera and Arduino COM port are exclusive-access resources.
- `pylonviewer` must be closed before YORU tries to open the Basler camera.
- `straight` and `standard_arduino` are different workflows:
  - `straight` expects a custom Arduino serial sketch
  - `standard_arduino` expects `StandardFirmata` on the Arduino
