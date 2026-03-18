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
- `capture_streamPylon.startCapture()` now loads the `.pfs` after opening the camera and before grabbing starts.
- Added GUI support for Basler `.pfs` selection and apply:
  - `yoru/libs/file_operation_realtime.py` now includes a `.pfs` file picker
  - `yoru/realtime_yoru_GUI.py` shows Basler-only controls for:
    - current `camera_pfs_path`
    - `Select .pfs`
    - `Apply .pfs`
    - live status text
  - the running pypylon capture loop can now reload `.pfs` settings on request without restarting the whole GUI
- Added shared runtime state in `yoru/libs/init_realtime.py` for:
  - `camera_pfs_reload_requested`
  - `camera_pfs_status`
  - `camera_pfs_last_loaded`
- `capture_streamPylon` now tracks `.pfs` apply status and reports:
  - no file selected
  - file not found
  - successful load
  - apply/restart failures
- Added `camera_pfs_path` to:
  - `config/template.yaml`
  - `config/yoru_default.yaml`
  - `config/yoru_pypylon_test.yaml`
  - `yoru/libs/init_realtime.py`

## Recording / save-after-live

- Implemented asynchronous recording in `yoru/libs/imager.py`.
- Added a queue-backed video writer helper so frames can:
  - continue feeding live YORU detection via `current_camera_frame`
  - also be copied into a recording queue for background writing
- Recording now flushes and closes more cleanly on stop/quit.
- Added export-path validation so recording cannot silently try to write to an invalid root path.
- If the export-folder dialog is canceled, the previous folder is now preserved.
- The realtime GUI now refuses to enable recording when no export folder is set.

## Trigger / Arduino changes

- Investigated both trigger modes:
  - `straight` for raw serial commands to a custom Arduino sketch
  - `standard_arduino` for Firmata-based direct pin control
- Fixed serial-only trigger handling in `yoru/libs/trigger.py` so serial plugins do not also try to open the port via the Firmata path.
- Added proper `close()` handling for serial trigger plugins so COM ports are released cleanly.
- Added terminal debug prints to `trigger_plugins/straight.py`:
  - serial port opened
  - `person detected`
  - `No person detected`
  - `Sending serial command: 1`
  - `Sending serial command: 0`
  - serial port closed
- Fixed `trigger_plugins/standard_arduino.py` by removing a bad import that caused plugin initialization to crash after opening the COM port.
- Updated trigger startup cleanup in `yoru/libs/trigger.py` so a plugin-init failure closes the already-opened Firmata port instead of leaving COM3 locked.

## Basler FPS visibility

- Added a direct Basler acquisition-rate readout in `capture_streamPylon.startCapture()`.
- YORU now attempts to read and print the camera-side rate from:
  - `ResultingFrameRate`
  - `AcquisitionFrameRate`
  - `AcquisitionFrameRateAbs`
- The value is also stored in `m_dict["camera_acquisition_fps"]`.
- This was added because the GUI FPS bar reflects YORU loop throughput, not necessarily the camera's true acquisition rate.
- Basler frame-rate writes now also try `AcquisitionFrameRateAbs` when `AcquisitionFrameRate` is unavailable.
- The startup log now prints which frame-rate node accepted the requested `camera_fps`, if any.

## Realtime GUI / startup fixes

- Fixed `config/yoru_default.yaml` so it parses correctly as YAML again.
- Updated `config/yoru_pypylon_test.yaml` so the sample `.pfs` path is blank by default instead of pointing to a machine-specific local path.
- `yoru/realtime_yoru_GUI.py` now supports `-c` / `--config` when launched directly.
- `run_gui_pypylon.bat` now:
  - starts from the repository directory
  - passes `--config config/yoru_pypylon_test.yaml`
  - avoids relying on a hard-coded user-specific conda activation path

## Test updates

- Added and/or updated tests around the pypylon backend in `tests/test_imager_pylon.py`.
- Added coverage for:
  - backend initialization
  - device selection
  - frame grabbing
  - cleanup
  - `.pfs` loading
  - async recorder frame copying
- Fixed script-style tests so pytest now reports real failures instead of treating boolean returns as success:
  - `tests/test_frame_grab.py`
  - `tests/test_camera_hardware.py`
  - `tests/test_video_recording.py`

## Test runs performed

- Verified:
  - `tests/test_imager_pylon.py`
  - `tests/test_imports.py`
  - `tests/test_frame_grab.py`
  - `tests/test_camera_hardware.py`
  - `tests/test_video_recording.py`
- Confirmed:
  - Basler hardware detection works
  - Basler frame grabbing works
  - video recording works and produces output files
  - the pypylon backend tests pass after the updates

## Config state for the pypylon live test file

- `config/yoru_pypylon_test.yaml` has been updated during this work to support:
  - Basler pypylon camera backend
  - optional `.pfs` loading
  - live trigger testing
- The exact trigger style/class/COM values may have been changed during debugging and should be checked before final use.

## Important operational notes

- Hardware-trigger tests and hardware-recording tests should be run sequentially, not in parallel, because the Basler camera and Arduino COM port are exclusive-access resources.
- `straight` and `standard_arduino` are different workflows:
  - `straight` expects a custom Arduino serial sketch
  - `standard_arduino` expects `StandardFirmata` on the Arduino
