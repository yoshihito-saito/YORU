import csv
import datetime
import os
import queue
import time
import tkinter as tk
from threading import Thread

import cv2
import mss
import numpy as np
from PIL import Image, ImageTk
from pynput import mouse

try:
    from pypylon import pylon
except ImportError:
    pylon = None


def _resize_frame(frame, resized_resolution):
    return cv2.resize(frame, resized_resolution)


def _ensure_three_channel_bgr(frame):
    if frame is None:
        return frame
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.ndim == 3 and frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


_RECORDING_STOP = object()


class _QueuedVideoWriter:
    def __init__(self, filename, fourcc, fps, frame_size, is_color):
        self.error = None
        self.closed = False
        self.queue = queue.Queue()
        self.writer = cv2.VideoWriter(filename, fourcc, fps, frame_size, is_color)
        if not self.writer.isOpened():
            raise RuntimeError(f"Failed to open video writer for {filename}")

        self.thread = Thread(target=self._drain_queue, daemon=True)
        self.thread.start()

    def _drain_queue(self):
        try:
            while True:
                frame = self.queue.get()
                if frame is _RECORDING_STOP:
                    break
                self.writer.write(frame)
        except Exception as exc:
            self.error = exc
        finally:
            self.writer.release()

    def write(self, frame):
        if self.closed:
            raise RuntimeError("Cannot write to a closed video recorder.")
        if self.error is not None:
            raise RuntimeError("Video recorder thread failed.") from self.error
        self.queue.put(frame.copy())

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.queue.put(_RECORDING_STOP)
        self.thread.join()
        if self.error is not None:
            raise RuntimeError("Video recorder thread failed.") from self.error


def _start_recording_session(owner):
    export_dir = str(owner.m_dict.get("export", "")).strip()
    if not export_dir:
        raise RuntimeError(
            "Recording export folder is not set. Select an export folder before enabling streaming."
        )

    export_dir = os.path.abspath(os.path.expanduser(os.path.expandvars(export_dir)))
    os.makedirs(export_dir, exist_ok=True)

    file_name_base = os.path.join(export_dir, owner.m_dict["curLog"])
    owner.curVidName = file_name_base + "_vid.avi"
    try:
        owner.vwriter = _QueuedVideoWriter(
            owner.curVidName,
            owner.fmt,
            owner.m_dict["camera_fps"],
            owner.resized_resolution,
            1,
        )

        owner.LogFile = open(file_name_base + "_log.csv", "a+", newline="")
        owner.log_writer = csv.writer(owner.LogFile)
        owner.log_writer.writerows([["frame", "total_time"]])

        owner.detectionlogfile = open(file_name_base + "_detect.csv", "a+", newline="")
        owner.rtesult_writer = csv.writer(owner.detectionlogfile)
        owner.rtesult_writer.writerows(
            [
                [
                    "x1",
                    "y1",
                    "x2",
                    "y2",
                    "confidence",
                    "class",
                    "class_name",
                    "total_time",
                ]
            ]
        )
    except Exception:
        _stop_recording_session(owner)
        raise


def _stop_recording_session(owner):
    close_error = None

    if getattr(owner, "vwriter", None) is not None:
        try:
            owner.vwriter.close()
        except Exception as exc:
            close_error = exc
        owner.vwriter = None

    if getattr(owner, "detectionlogfile", None) is not None:
        owner.detectionlogfile.close()
        owner.detectionlogfile = None

    if getattr(owner, "LogFile", None) is not None:
        owner.LogFile.close()
        owner.LogFile = None

    if close_error is not None:
        raise close_error


class capture_streamCV2:
    def __init__(self, srcCam=1, m_dict={}):
        print("CV-initialization...")
        self.m_dict = m_dict
        self.src = srcCam
        self.t0 = self.m_dict["t0"]
        self.default_FPS = self.m_dict["camera_fps"]
        self.resized_resolution = (
            int(self.m_dict["camera_width"] * self.m_dict["camera_scale"]),
            int(self.m_dict["camera_height"] * self.m_dict["camera_scale"]),
        )

        self.frameBufLen = 200
        self.frameBuffer = np.zeros(
            (self.resized_resolution[1], self.resized_resolution[0], self.frameBufLen),
            dtype="uint8",
        )
        self.fmt = cv2.VideoWriter_fourcc("D", "I", "V", "X")
        self.vwriter = None
        self.LogFile = None
        self.detectionlogfile = None
        print("CV-initialization Finished")

    def startCapture(self):
        print("CV-capture start...")
        self.capture = cv2.VideoCapture(self.src + cv2.CAP_DSHOW)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.m_dict["camera_width"])
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.m_dict["camera_height"])
        print(self.m_dict["camera_fps"])
        self.capture.set(cv2.CAP_PROP_FPS, self.m_dict["camera_fps"])
        self.capture.set(cv2.CAP_PROP_SETTINGS, 1)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 2000)
        (status, frame) = self.capture.read()
        print(status)
        halfImg = _resize_frame(frame, self.resized_resolution)
        print("CV-capture start success")

    def run(self):
        self.startCapture()
        t0 = time.perf_counter()
        stream_flag = False
        self.frame_count = 0
        while True:
            now = datetime.datetime.now()
            if (not stream_flag) & self.m_dict["stream"]:
                _start_recording_session(self)
                stream_flag = True
                print("Start: Video-streaming")

            elif stream_flag & (not self.m_dict["stream"]):
                self.frame_count = 0
                # Streaming Done.
                stream_flag = False
                _stop_recording_session(self)
                print(self.curVidName)
                print("Finished: Video-streaming")

            # Ensure camera is connected
            if self.capture.isOpened():
                (status, frame) = self.capture.read()
                t1 = time.perf_counter()
                self.m_dict["total_time"] = t1 - self.m_dict["t0"]
                halfImg = _resize_frame(frame, self.resized_resolution)

                if status:
                    if self.m_dict["camera_imshow"]:
                        cv2.imshow("frame", halfImg)
                    if self.m_dict["stream"] & stream_flag:
                        self.vwriter.write(halfImg)
                        "# Date, total time, Count, Speed, Position, Dark, Z-stage, di"
                        # self.currentLogFile.write(
                        #     str(now) + ", " + str(self.m_dict["total_time"]) + "\r"
                        # )
                        self.log_writer.writerows(
                            [[self.frame_count, str(self.m_dict["total_time"])]]
                        )
                        if self.m_dict["yolo_process_state"]:
                            self.rtesult_writer.writerows(self.m_dict["yolo_results"])
                        self.frame_count += 1
                else:
                    break
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                elif self.m_dict["quit"]:
                    break
                self.m_dict["current_camera_frame"] = halfImg
            else:
                t1 = time.perf_counter()
            # while (t1-t0) < 1/(self.default_FPS+1.0):
            #     t1 = time.perf_counter()
            self.m_dict["camera_fps"] = int(1 / (t1 - t0))
            t0 = t1 * 1
            if self.m_dict["quit"]:
                break

        if stream_flag:
            _stop_recording_session(self)

    def run_Buffering(self):
        # TODO: faster buffering and exporting
        self.startCapture()
        k = 0
        self.frameTimeStamp = np.zeros((self.frameBufLen))
        while not self.m_dict["quit"]:
            self.frameTimeStamp[k % self.frameBufLen] = time.perf_counter() - self.t0
            (status, frame) = self.capture.read()
            self.m_dict["currentFrame"] = frame
            self.frameBuffer[:, :, :, k % self.frameBufLen] = frame
            self.fps = self.frameBufLen / (
                np.max(self.frameTimeStamp) - np.min(self.frameTimeStamp)
            )
            k = k + 1

    def __del__(self):
        if getattr(self, "vwriter", None) is not None:
            try:
                _stop_recording_session(self)
            except Exception:
                pass
        if hasattr(self, "capture") and self.capture is not None:
            self.capture.release()
        try:
            cv2.destroyAllWindows()
        except ImportError:
            pass


class capture_streamPylon:
    def __init__(self, srcCam=0, m_dict={}):
        print("Pylon-initialization...")
        if pylon is None:
            raise ImportError(
                "pypylon is not installed. Install it before using the Basler camera backend."
            )

        self.m_dict = m_dict
        self.src = srcCam
        self.t0 = self.m_dict["t0"]
        self.default_FPS = self.m_dict["camera_fps"]
        self.resized_resolution = (
            int(self.m_dict["camera_width"] * self.m_dict["camera_scale"]),
            int(self.m_dict["camera_height"] * self.m_dict["camera_scale"]),
        )

        self.frameBufLen = 200
        self.frameBuffer = np.zeros(
            (self.resized_resolution[1], self.resized_resolution[0], self.frameBufLen),
            dtype="uint8",
        )
        self.fmt = cv2.VideoWriter_fourcc("D", "I", "V", "X")
        self.capture = None
        self.converter = None
        self.vwriter = None
        self.LogFile = None
        self.detectionlogfile = None
        print("Pylon-initialization Finished")

    def _configure_converter(self):
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    def _select_device(self):
        factory = pylon.TlFactory.GetInstance()
        devices = factory.EnumerateDevices()
        if not devices:
            raise RuntimeError("No Basler camera detected by pypylon.")

        serial = self.m_dict.get("camera_serial", "")
        if serial:
            for device in devices:
                if device.GetSerialNumber() == serial:
                    return factory.CreateDevice(device)
            raise RuntimeError(f"Basler camera with serial '{serial}' was not found.")

        camera_index = int(self.m_dict.get("camera_id", 0))
        if camera_index >= len(devices):
            raise RuntimeError(
                f"Configured camera_id {camera_index} exceeds detected Basler cameras ({len(devices)})."
            )
        return factory.CreateDevice(devices[camera_index])

    def _grab_frame(self):
        grab_result = self.capture.RetrieveResult(
            5000, pylon.TimeoutHandling_ThrowException
        )
        try:
            if not grab_result.GrabSucceeded():
                raise RuntimeError("Basler frame grab failed.")

            image = self.converter.Convert(grab_result)
            frame = image.GetArray()
            return _ensure_three_channel_bgr(frame)
        finally:
            grab_result.Release()

    def _load_pfs_configuration(self):
        pfs_path = str(self.m_dict.get("camera_pfs_path", "")).strip()
        if not pfs_path:
            self.m_dict["camera_pfs_status"] = "No .pfs file selected"
            self.m_dict["camera_pfs_last_loaded"] = ""
            return

        pfs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(pfs_path)))
        if not os.path.isfile(pfs_path):
            self.m_dict["camera_pfs_status"] = f".pfs not found: {pfs_path}"
            raise FileNotFoundError(
                f"Configured Basler .pfs file was not found: {pfs_path}"
            )

        feature_persistence = getattr(pylon, "FeaturePersistence", None)
        if feature_persistence is None:
            self.m_dict["camera_pfs_status"] = "pypylon FeaturePersistence unavailable"
            raise RuntimeError(
                "pypylon does not expose FeaturePersistence; cannot load Basler .pfs settings."
            )

        feature_persistence.Load(pfs_path, self.capture.GetNodeMap(), True)
        self.m_dict["camera_pfs_path"] = pfs_path
        self.m_dict["camera_pfs_last_loaded"] = pfs_path
        self.m_dict["camera_pfs_status"] = f"Loaded .pfs: {os.path.basename(pfs_path)}"

    def _read_camera_acquisition_rate(self):
        rate_nodes = (
            "ResultingFrameRate",
            "AcquisitionFrameRate",
            "AcquisitionFrameRateAbs",
        )
        for node_name in rate_nodes:
            try:
                node = getattr(self.capture, node_name, None)
                if node is None:
                    continue
                value = float(node.GetValue())
                self.m_dict["camera_acquisition_fps"] = value
                return value, node_name
            except Exception:
                continue

        self.m_dict["camera_acquisition_fps"] = None
        return None, None

    def _set_camera_frame_rate(self):
        target_fps = float(self.m_dict["camera_fps"])

        try:
            rate_enable = getattr(self.capture, "AcquisitionFrameRateEnable", None)
            if rate_enable is not None:
                rate_enable.SetValue(True)
        except Exception:
            pass

        for node_name in ("AcquisitionFrameRate", "AcquisitionFrameRateAbs"):
            try:
                node = getattr(self.capture, node_name, None)
                if node is None:
                    continue
                node.SetValue(target_fps)
                return node_name
            except Exception:
                continue

        return None

    def _apply_camera_geometry(self):
        # Keep YORU's output resolution contract even if a .pfs changes sensor settings.
        try:
            self.capture.Width.SetValue(
                min(self.capture.Width.Max, int(self.m_dict["camera_width"]))
            )
        except Exception:
            pass

        try:
            self.capture.Height.SetValue(
                min(self.capture.Height.Max, int(self.m_dict["camera_height"]))
            )
        except Exception:
            pass

    def _reload_pfs_if_requested(self):
        if not self.m_dict.get("camera_pfs_reload_requested", False):
            return

        self.m_dict["camera_pfs_reload_requested"] = False
        if not str(self.m_dict.get("camera_pfs_path", "")).strip():
            self.m_dict["camera_pfs_status"] = "Select a .pfs file before applying"
            return

        was_grabbing = self.capture is not None and self.capture.IsGrabbing()
        try:
            if was_grabbing:
                self.capture.StopGrabbing()

            self._load_pfs_configuration()
            self._apply_camera_geometry()
            self._set_camera_frame_rate()
            self._configure_converter()
            print(f"Applied Basler .pfs: {self.m_dict['camera_pfs_last_loaded']}")
        except Exception as exc:
            self.m_dict["camera_pfs_status"] = f"Failed to apply .pfs: {exc}"
            print(self.m_dict["camera_pfs_status"])
        finally:
            if was_grabbing and self.capture is not None and not self.capture.IsGrabbing():
                try:
                    self.capture.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                except Exception as exc:
                    self.m_dict["camera_pfs_status"] = (
                        f"Camera restart failed after .pfs apply: {exc}"
                    )
                    print(self.m_dict["camera_pfs_status"])

    def startCapture(self):
        print("Pylon-capture start...")
        self.capture = pylon.InstantCamera(self._select_device())
        self.capture.Open()
        self._load_pfs_configuration()

        self._apply_camera_geometry()
        frame_rate_node = self._set_camera_frame_rate()

        self._configure_converter()

        self.capture.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        frame = self._grab_frame()
        _resize_frame(frame, self.resized_resolution)
        if frame_rate_node is not None:
            print(
                f"Basler frame-rate target requested via {frame_rate_node}: "
                f"{float(self.m_dict['camera_fps']):.2f} fps"
            )
        else:
            print("Basler frame-rate target could not be set from camera_fps")
        acquisition_fps, acquisition_node = self._read_camera_acquisition_rate()
        if acquisition_fps is not None:
            print(
                f"Basler acquisition rate ({acquisition_node}): {acquisition_fps:.2f} fps"
            )
        else:
            print("Basler acquisition rate: unavailable")
        print("Pylon-capture start success")

    def run(self):
        self.startCapture()
        t0 = time.perf_counter()
        stream_flag = False
        self.frame_count = 0
        while True:
            now = datetime.datetime.now()
            if (not stream_flag) & self.m_dict["stream"]:
                _start_recording_session(self)
                stream_flag = True
                print("Start: Video-streaming")

            elif stream_flag & (not self.m_dict["stream"]):
                self.frame_count = 0
                stream_flag = False
                _stop_recording_session(self)
                print(self.curVidName)
                print("Finished: Video-streaming")

            self._reload_pfs_if_requested()

            if self.capture is not None and self.capture.IsGrabbing():
                frame = self._grab_frame()
                t1 = time.perf_counter()
                self.m_dict["total_time"] = t1 - self.m_dict["t0"]
                halfImg = _resize_frame(frame, self.resized_resolution)

                if self.m_dict["camera_imshow"]:
                    cv2.imshow("frame", halfImg)
                if self.m_dict["stream"] & stream_flag:
                    self.vwriter.write(halfImg)
                    self.log_writer.writerows(
                        [[self.frame_count, str(self.m_dict["total_time"])]]
                    )
                    if self.m_dict["yolo_process_state"]:
                        self.rtesult_writer.writerows(self.m_dict["yolo_results"])
                    self.frame_count += 1

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                elif self.m_dict["quit"]:
                    break
                self.m_dict["current_camera_frame"] = halfImg
            else:
                t1 = time.perf_counter()

            self.m_dict["camera_fps"] = int(1 / (t1 - t0))
            t0 = t1 * 1
            if self.m_dict["quit"]:
                break

        if stream_flag:
            _stop_recording_session(self)

    def __del__(self):
        if getattr(self, "vwriter", None) is not None:
            try:
                _stop_recording_session(self)
            except Exception:
                pass
        if hasattr(self, "capture") and self.capture is not None:
            try:
                if self.capture.IsGrabbing():
                    self.capture.StopGrabbing()
                if self.capture.IsOpen():
                    self.capture.Close()
            except Exception:
                pass
        try:
            cv2.destroyAllWindows()
        except ImportError:
            pass


class capture_streamMSS:
    def __init__(self, m_dict={}):
        print("CV-initialization...")
        self.m_dict = m_dict
        self.initialized = False  # Add this line

        self.disp = m_dict["capture_area"]
        self.t0 = self.m_dict["t0"]
        self.resized_resolution = (
            int(self.m_dict["camera_width"] * self.m_dict["camera_scale"]),
            int(self.m_dict["camera_height"] * self.m_dict["camera_scale"]),
        )

        self.frameBufLen = 200
        self.frameBuffer = np.zeros(
            (self.resized_resolution[1], self.resized_resolution[0], self.frameBufLen),
            dtype="uint8",
        )
        self.fmt = cv2.VideoWriter_fourcc("D", "I", "V", "X")
        self.vwriter = None
        self.LogFile = None
        self.detectionlogfile = None
        print("CV-initialization Finished")

    def startCapture(self):
        self.src = mss.mss()
        frame = np.array(self.src.grab(self.disp))
        halfImg = cv2.resize(frame, self.resized_resolution)
        print("CV-capture start success")

    def run(self):
        self.startCapture()
        t0 = time.perf_counter()
        stream_flag = False
        self.frame_count = 0
        while True:
            now = datetime.datetime.now()
            if (not stream_flag) & self.m_dict["stream"]:
                _start_recording_session(self)
                stream_flag = True
                print("Start: Video-streaming")
            elif stream_flag & (not self.m_dict["stream"]):
                self.frame_count = 0
                # Streaming Done.
                stream_flag = False
                _stop_recording_session(self)
                print(self.curVidName)
                print("Finished: Video-streaming")

            # Ensure camera is connected
            if True:  # self.capture.isOpened():
                # (status, frame) = mss.capture.read()
                frame = np.array(self.src.grab(self.disp)) * 1
                t1 = time.perf_counter()
                self.m_dict["total_time"] = t1 - self.m_dict["t0"]
                halfImg = cv2.resize(frame, self.resized_resolution)

                if True:
                    if self.m_dict["camera_imshow"]:
                        cv2.imshow("frame", halfImg)
                    if self.m_dict["stream"] & stream_flag:
                        self.vwriter.write(halfImg)
                        "# Date, total time, Count, Speed, Position, Dark, Z-stage, di"
                        # self.currentLogFile.write(
                        #     str(now) + ", " + str(self.m_dict["total_time"]) + "\r"
                        # )
                        self.log_writer.writerows(
                            [[self.frame_count, str(self.m_dict["total_time"])]]
                        )
                        if self.m_dict["yolo_process_state"]:
                            self.rtesult_writer.writerows(self.m_dict["yolo_results"])
                        self.frame_count += 1

                else:
                    break
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                elif self.m_dict["quit"]:
                    break
                self.m_dict["current_camera_frame"] = halfImg
            else:
                t1 = time.perf_counter()
            while (t1 - t0) < 1 / 16:  # TODO
                t1 = time.perf_counter()
            self.m_dict["camera_fps"] = int(1 / (t1 - t0))
            t0 = t1 * 1

            if self.m_dict["quit"]:
                break

        if stream_flag:
            _stop_recording_session(self)

    def run_Buffering(self):
        # TODO: faster buffering and exporting
        self.startCapture()
        k = 0
        self.frameTimeStamp = np.zeros((self.frameBufLen))
        while not self.m_dict["quit"]:
            self.frameTimeStamp[k % self.frameBufLen] = time.perf_counter() - self.t0
            frame = self.src.grab(self.disp)
            self.m_dict["currentFrame"] = np.array(frame)
            self.frameBuffer[:, :, :, k % self.frameBufLen] = frame
            self.fps = self.frameBufLen / (
                np.max(self.frameTimeStamp) - np.min(self.frameTimeStamp)
            )
            k = k + 1

    def __del__(self):
        if getattr(self, "vwriter", None) is not None:
            try:
                _stop_recording_session(self)
            except Exception:
                pass
        if hasattr(self, "capture") and self.capture is not None:
            self.capture.release()
        try:
            cv2.destroyAllWindows()
        except ImportError:
            pass


class SelectCaptureArea:
    def __init__(self, root, opacity=0.5, m_dict={}):
        print("select area")
        self.m_dict = m_dict
        self.m_dict["capture_area"] = {}

        self.root = root
        self.color = (219, 77, 109)  # Added color parameter
        self.opacity = opacity
        self.canvas = tk.Canvas(
            root, width=root.winfo_screenwidth(), height=root.winfo_screenheight()
        )
        self.canvas.pack()

        self.start_x = None
        self.start_y = None
        self.rectangle = None

        self.root.attributes("-alpha", 0.2)  # Start fully transparent
        self.root.attributes("-fullscreen", True)  # Fullscreen
        self.root.update()  # Make sure the window is shown

        self.listener = mouse.Listener(on_click=self.on_click, on_move=self.on_move)
        self.listener.start()

    def draw_rectangle(self, start_x, start_y, end_x, end_y):
        if start_x > end_x:
            start_x, end_x = end_x, start_x
        if start_y > end_y:
            start_y, end_y = end_y, start_y
        image = Image.new(
            "RGBA",
            (end_x - start_x, end_y - start_y),
            (*self.color, int(255 * self.opacity)),
        )
        self.photo = ImageTk.PhotoImage(image)
        self.rectangle = self.canvas.create_image(
            start_x, start_y, image=self.photo, anchor="nw"
        )

    def on_click(self, x, y, button, pressed):
        if button == mouse.Button.left:
            if pressed:
                self.start_x = x
                self.start_y = y
                self.top = y
                self.left = x
                self.root.attributes(
                    "-alpha", 0.2
                )  # Make visible when we start the drag
            else:
                self.canvas.delete(self.rectangle)
                if y > self.top and x > self.left:
                    self.width = x - self.left
                    self.height = y - self.top
                else:
                    self.width = self.left - x
                    self.height = self.top - y
                    self.top = y
                    self.left = x
                self.m_dict["capture_area"]["top"] = self.top
                self.m_dict["capture_area"]["left"] = self.left
                self.m_dict["capture_area"]["width"] = self.width
                self.m_dict["capture_area"]["height"] = self.height
                # self.m_dict["camera_width"] = self.width
                # self.m_dict["camera_height"] = self.height
                self.m_dict["camera_width"] = 640
                self.m_dict["camera_height"] = 480
                self.m_dict["capture_area"] = {
                    "top": self.top,
                    "left": self.left,
                    "width": self.width,
                    "height": self.height,
                }
                print(self.m_dict["capture_area"])
                self.root.quit()  # Close the window when we release the mouse button

    def on_move(self, x, y):
        if self.start_x is not None and self.start_y is not None:
            if self.rectangle is not None:
                self.canvas.delete(self.rectangle)
            self.draw_rectangle(self.start_x, self.start_y, x, y)


class select_run:
    def __init__(self, m_dict):
        self.m_dict = m_dict

    def main(self):
        # select capture area
        if self.m_dict["capture_area_select"]:  # Modify this line
            self.root = tk.Tk()
            self.area = SelectCaptureArea(self.root, m_dict=self.m_dict)
            self.root.mainloop()
            self.area.listener.stop()
            self.root.destroy()
            self.initialized = True  # Add this line


if __name__ == "__main__":
    d = {}
    d["t0"] = time.perf_counter()
    d["capture_area"] = {"top": 0, "left": 0, "width": 640, "height": 480}
    d["capture_area_select"] = True
    d["camera_id"] = 1
    d["camera_width"] = 1280
    d["camera_height"] = 960
    d["camera_scale"] = 1
    d["camera_fps"] = 20
    d["export"] = "test\\"
    d["curLog"] = "hoge.txt"
    d["camera_imshow"] = True
    d["stream"] = False
    d["quit"] = False
    d["stream_MSS"] = False
    if d["stream_MSS"]:
        SR = select_run(m_dict=d)
        SR.main()
        imgWin = capture_streamMSS(m_dict=d)

    else:
        imgWin = capture_streamCV2(m_dict=d)
    imgWin.run()
