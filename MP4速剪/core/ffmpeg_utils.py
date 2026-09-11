"""FFmpeg 剪輯核心模組 - 使用 stream copy 實現極速剪接"""

import os
import subprocess
import shutil
import json
import tempfile
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass

def _find_ffmpeg() -> Tuple[str, str]:
    """尋找 ffmpeg 與 ffprobe 可執行檔"""
    # 重新檢查目前 PATH（支援動態安裝後）
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")

    # 常見安裝位置
    candidates = [
        os.path.join(project_root, "ffmpeg", "bin"),
        os.path.join(project_root, "ffmpeg"),
        project_root,
        os.path.join(local_app_data, "Microsoft", "WinGet", "Links"),
        r"C:\ffmpeg\bin",
        r"C:\ffmpeg",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files\ffmpeg",
        r"C:\Program Files (x86)\ffmpeg\bin",
        os.path.join(local_app_data, "ffmpeg", "bin"),
        os.path.join(local_app_data, "ffmpeg"),
        os.path.join(user_profile, "scoop", "shims"),
        r"C:\ProgramData\chocolatey\bin",
    ]

    # 也搜尋 WinGet Packages 中是否有 Gyan.FFmpeg
    winget_pkg_dir = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_pkg_dir):
        try:
            for entry in os.listdir(winget_pkg_dir):
                if "ffmpeg" in entry.lower():
                    pkg_path = os.path.join(winget_pkg_dir, entry)
                    for root, dirs, files in os.walk(pkg_path):
                        if "ffmpeg.exe" in files:
                            candidates.append(root)
        except Exception:
            pass

    found_f = ffmpeg
    found_p = ffprobe

    for folder in candidates:
        if not folder or not os.path.isdir(folder):
            continue
        f = os.path.join(folder, "ffmpeg.exe")
        p = os.path.join(folder, "ffprobe.exe")
        if not found_f and os.path.isfile(f):
            found_f = f
        if not found_p and os.path.isfile(p):
            found_p = p
        if found_f and found_p:
            return found_f, found_p

    if found_f and not found_p:
        found_p = found_f.replace("ffmpeg.exe", "ffprobe.exe")

    return found_f or "ffmpeg", found_p or "ffprobe"


def get_ffmpeg_paths() -> Tuple[str, str]:
    """動態取得目前的 ffmpeg 與 ffprobe 路徑"""
    global FFMPEG_PATH, FFPROBE_PATH
    f, p = _find_ffmpeg()
    FFMPEG_PATH, FFPROBE_PATH = f, p
    return f, p


FFMPEG_PATH, FFPROBE_PATH = _find_ffmpeg()


@dataclass
class VideoInfo:
    """影片基本資訊"""
    path: str
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    size_bytes: int


@dataclass
class Segment:
    """保留片段（開始時間、結束時間，單位：秒）"""
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start

    def __repr__(self):
        return f"Segment({self.start:.3f}s ~ {self.end:.3f}s)"


def _format_concat_line(file_path: str) -> str:
    """格式化適用於 ffmpeg concat demuxer 的路徑（Windows 反斜線需轉為正斜線並跳脫單引號）"""
    escaped = os.path.abspath(file_path).replace("\\", "/").replace("'", "'\\''")
    return f"file '{escaped}'\n"


def get_video_info(path: str) -> Optional[VideoInfo]:
    """快速取得影片資訊（使用 ffprobe）"""
    try:
        _, ffprobe_bin = get_ffmpeg_paths()
        cmd = [
            ffprobe_bin, "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            path
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=10, creationflags=_no_window_flag()
        )
        data = json.loads(result.stdout)

        duration = 0.0
        try:
            duration = float(data.get("format", {}).get("duration", 0) or 0)
        except (ValueError, TypeError):
            duration = 0.0

        size = 0
        try:
            size = int(data.get("format", {}).get("size", 0) or 0)
        except (ValueError, TypeError):
            size = 0

        width = height = 0
        fps = 30.0
        vcodec = acodec = ""

        for stream in data.get("streams", []):
            if duration <= 0:
                try:
                    d = float(stream.get("duration", 0) or 0)
                    if d > 0:
                        duration = d
                except (ValueError, TypeError):
                    pass

            if stream.get("codec_type") == "video" and not width:
                width = int(stream.get("width", 0) or 0)
                height = int(stream.get("height", 0) or 0)
                vcodec = stream.get("codec_name", "")
                r_frame_rate = stream.get("r_frame_rate", "30/1")
                try:
                    n, d = r_frame_rate.split("/")
                    fps = float(n) / float(d) if float(d) else 30.0
                except Exception:
                    fps = 30.0
            elif stream.get("codec_type") == "audio" and not acodec:
                acodec = stream.get("codec_name", "")

        return VideoInfo(
            path=path,
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            video_codec=vcodec,
            audio_codec=acodec,
            size_bytes=size,
        )
    except Exception as e:
        print(f"[get_video_info] error: {e}")
        return None


def cut_segments(
    input_path: str,
    output_path: str,
    segments: List[Segment],
    progress_callback: Optional[Callable[[int, str], None]] = None,
    use_concat: bool = True,
) -> bool:
    """
    快速剪接指定片段並輸出（stream copy，無重新編碼）
    segments: 要「保留」的片段列表
    """
    if not segments:
        return False

    ffmpeg_bin, _ = get_ffmpeg_paths()

    try:
        if len(segments) == 1:
            # 只有一段：直接用 -ss -to 加 stream copy，最快
            seg = segments[0]
            if progress_callback:
                progress_callback(30, "正在剪輯片段...")
            cmd = [
                ffmpeg_bin, "-y",
                "-ss", str(seg.start),
                "-to", str(seg.end),
                "-i", input_path,
                "-c", "copy",
                "-avoid_negative_ts", "1",
                output_path
            ]
            _run_ffmpeg(cmd)
            if progress_callback:
                progress_callback(100, "完成！")
        else:
            # 多段：先切出暫存檔，再用 concat demuxer 合併
            _cut_multi_segments(input_path, output_path, segments, progress_callback)
        return True
    except Exception as e:
        print(f"[cut_segments] error: {e}")
        return False


def _cut_multi_segments(
    input_path: str,
    output_path: str,
    segments: List[Segment],
    progress_callback: Optional[Callable[[int, str], None]] = None,
):
    """多段剪接：分段切割後合併"""
    ffmpeg_bin, _ = get_ffmpeg_paths()
    tmp_dir = tempfile.mkdtemp(prefix="mp4cut_")
    concat_list_path = os.path.join(tmp_dir, "concat.txt")
    tmp_files = []

    try:
        total = len(segments)
        for i, seg in enumerate(segments):
            tmp_file = os.path.join(tmp_dir, f"seg_{i:04d}.mp4")
            tmp_files.append(tmp_file)
            cmd = [
                ffmpeg_bin, "-y",
                "-ss", str(seg.start),
                "-to", str(seg.end),
                "-i", input_path,
                "-c", "copy",
                "-avoid_negative_ts", "1",
                tmp_file
            ]
            _run_ffmpeg(cmd)
            if progress_callback:
                pct = int((i + 1) / total * 80)
                progress_callback(pct, f"剪切片段 {i+1}/{total}...")

        # 寫 concat 清單（使用轉義後的路徑）
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for tf in tmp_files:
                f.write(_format_concat_line(tf))

        if progress_callback:
            progress_callback(85, "合併片段中...")

        # 用 concat demuxer 合併（stream copy）
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        _run_ffmpeg(cmd)

        if progress_callback:
            progress_callback(100, "完成！")

    finally:
        # 清理暫存
        for tf in tmp_files:
            try:
                os.remove(tf)
            except Exception:
                pass
        try:
            os.remove(concat_list_path)
        except Exception:
            pass
        try:
            os.rmdir(tmp_dir)
        except Exception:
            pass


def merge_files(
    input_paths: List[str],
    output_path: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> bool:
    """批量合併多個 MP4 檔案（stream copy）"""
    if not input_paths:
        return False
    ffmpeg_bin, _ = get_ffmpeg_paths()
    tmp_dir = None
    concat_list_path = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="mp4merge_")
        concat_list_path = os.path.join(tmp_dir, "merge.txt")

        with open(concat_list_path, "w", encoding="utf-8") as f:
            for p in input_paths:
                f.write(_format_concat_line(p))

        if progress_callback:
            progress_callback(10, "開始合併...")

        cmd = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        _run_ffmpeg(cmd)

        if progress_callback:
            progress_callback(100, "合併完成！")

        return True
    except Exception as e:
        print(f"[merge_files] error: {e}")
        return False
    finally:
        if concat_list_path and os.path.isfile(concat_list_path):
            try:
                os.remove(concat_list_path)
            except Exception:
                pass
        if tmp_dir and os.path.isdir(tmp_dir):
            try:
                os.rmdir(tmp_dir)
            except Exception:
                pass


def _run_ffmpeg(cmd: List[str], progress_callback=None):
    """執行 ffmpeg 指令"""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_no_window_flag(),
    )
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{stderr}")


def _no_window_flag() -> int:
    """Windows: 隱藏 ffmpeg 視窗"""
    try:
        import subprocess
        return subprocess.CREATE_NO_WINDOW
    except AttributeError:
        return 0


def check_ffmpeg() -> bool:
    """檢查 ffmpeg 是否可用"""
    try:
        ffmpeg_bin, _ = get_ffmpeg_paths()
        r = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True, timeout=15,
            creationflags=_no_window_flag()
        )
        return r.returncode == 0
    except Exception:
        return False
