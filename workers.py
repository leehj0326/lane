"""LANE: 백그라운드에서 돌리는 일 전부.

- JobManager: 스레드 실행, 진행률, 취소, 중복 방지, 메인 스레드 콜백
- analyze(): 곡 ID -> (필요하면 ffmpeg 변환) -> 분석 -> 캐시
- AnalysisService: 메뉴가 쓰는 창구

규칙: 여기 코드는 화면이나 게임 상태를 건드리지 않는다. 결과는 poll()을 통해
메인 스레드에서 받는다.
"""
import bisect
import hashlib
import itertools
import math
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import traceback
import wave
from concurrent.futures import ThreadPoolExecutor
import json

import numpy as np

import config as C


# ============================================================
# 비동기 작업 관리자
# ============================================================

QUEUED, RUNNING, DONE, FAILED, CANCELLED = (
    "queued", "running", "done", "failed", "cancelled")


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, job_id, name, key, on_done):
        self.id = job_id
        self.name = name
        self.key = key
        self.on_done = on_done
        self.state = QUEUED
        self.progress = 0.0
        self.message = ""
        self.result = None
        self.error = None
        self.traceback = None
        self.cancel_event = threading.Event()

    @property
    def active(self):
        return self.state in (QUEUED, RUNNING)


class JobContext:
    """작업 함수에 넘겨지는 객체. 워커 스레드에서만 쓴다."""

    def __init__(self, job):
        self._job = job

    def report(self, progress, message=None):
        self._job.progress = max(0.0, min(1.0, float(progress)))
        if message is not None:
            self._job.message = message

    @property
    def cancelled(self):
        return self._job.cancel_event.is_set()

    def check(self):
        if self.cancelled:
            raise Cancelled()


class JobManager:
    def __init__(self, workers=1):
        self._pool = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="job")
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._jobs = []
        self._finished = queue.Queue()

    # ---- 제출 / 취소 ----
    def submit(self, name, fn, *args, key=None, on_done=None):
        """같은 key의 작업이 이미 진행 중이면 새로 만들지 않고 그 작업을 돌려준다."""
        with self._lock:
            if key is not None:
                for job in self._jobs:
                    if job.key == key and job.active:
                        return job
            job = Job(next(self._ids), name, key, on_done)
            self._jobs.append(job)
        self._pool.submit(self._run, job, fn, args)
        return job

    def cancel(self, job):
        job.cancel_event.set()

    def cancel_all(self):
        with self._lock:
            for job in self._jobs:
                if job.active:
                    job.cancel_event.set()

    def find(self, key):
        """key에 해당하는 가장 최근 작업 (진행 중이거나 막 끝난 것)."""
        with self._lock:
            for job in reversed(self._jobs):
                if job.key == key:
                    return job
        return None

    # ---- 워커 스레드 ----
    def _run(self, job, fn, args):
        if job.cancel_event.is_set():
            job.state = CANCELLED
            self._finished.put(job)
            return
        job.state = RUNNING
        try:
            job.result = fn(JobContext(job), *args)
            job.progress = 1.0
            job.state = DONE
        except Cancelled:
            job.state = CANCELLED
        except Exception as exc:  # noqa: BLE001
            job.error = f"{type(exc).__name__}: {exc}"
            job.traceback = traceback.format_exc()
            job.state = FAILED
        self._finished.put(job)

    # ---- 메인 스레드 ----
    def poll(self):
        """끝난 작업의 on_done을 호출하고 그 목록을 돌려준다."""
        done = []
        while True:
            try:
                job = self._finished.get_nowait()
            except queue.Empty:
                break
            done.append(job)
            if job.on_done:
                job.on_done(job)
        if done:
            with self._lock:
                self._jobs = [j for j in self._jobs if j.active]
                # 방금 끝난 작업도 find()로 한 번은 볼 수 있게 유지
                self._jobs.extend(done)
        return done

    def forget(self, job):
        with self._lock:
            if job in self._jobs and not job.active:
                self._jobs.remove(job)

    def shutdown(self, cancel=True):
        if cancel:
            self.cancel_all()
        self._pool.shutdown(wait=True, cancel_futures=True)

# ============================================================
# ffmpeg 연결 (없으면 안내)
# ============================================================

NEEDS_FFMPEG_MSG = "wav 이외의 형식은 ffmpeg가 필요해요 (mp3 변환, 영상 소리 추출)"


class FfmpegMissing(Exception):
    pass


def ffmpeg_path():
    return shutil.which("ffmpeg")


def is_wav(path):
    return path.lower().endswith(".wav")


def decode_to_wav(src, ctx=None):
    """분석용 임시 wav를 만든다. 호출한 쪽이 지워야 한다."""
    exe = ffmpeg_path()
    if not exe:
        raise FfmpegMissing(NEEDS_FFMPEG_MSG)
    fd, out = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = [exe, "-y", "-v", "error", "-i", src, "-vn", "-map", "0:a:0",
           "-ac", "1", "-ar", "22050", out]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        os.remove(out)
        if "does not contain any stream" in proc.stderr or "matches no streams" in proc.stderr:
            raise ValueError("소리가 없는 파일이에요")
        raise ValueError("소리를 변환하지 못했어요")
    return out


def to_mp3(src, dst):
    """wav/ogg/flac/영상 -> mp3. 이미 mp3면 호출하지 말 것(이중 압축 방지)."""
    exe = ffmpeg_path()
    if not exe:
        raise FfmpegMissing(NEEDS_FFMPEG_MSG)
    cmd = [exe, "-y", "-v", "error", "-i", src, "-vn", "-map", "0:a:0",
           "-codec:a", "libmp3lame", "-q:a", "2", dst]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        raise ValueError("mp3로 변환하지 못했어요")

# ============================================================
# wav 스트리밍 읽기, 곡 ID(해시)
# ============================================================

PAD = 256


class AudioError(Exception):
    pass


def file_sha256(path, ctx=None, progress_range=(0.0, 1.0), block=1 << 20):
    """원본 파일 바이트의 해시 = 곡 ID."""
    size = max(1, os.path.getsize(path))
    done = 0
    h = hashlib.sha256()
    lo, hi = progress_range
    with open(path, "rb") as f:
        while True:
            data = f.read(block)
            if not data:
                break
            h.update(data)
            done += len(data)
            if ctx:
                ctx.check()
                ctx.report(lo + (hi - lo) * done / size)
    return h.hexdigest()


def wav_info(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
    except (wave.Error, EOFError) as exc:
        raise AudioError(f"읽을 수 없는 wav 파일이에요 ({exc})") from exc


def duration_ms(path):
    sr, _, _, n = wav_info(path)
    return int(round(n * 1000 / sr))


def _to_mono_float(raw, sampwidth, channels):
    if sampwidth == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sampwidth == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sampwidth == 3:
        a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (a[:, 0].astype(np.int32) | (a[:, 1].astype(np.int32) << 8)
             | (a[:, 2].astype(np.int32) << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v)
        x = v.astype(np.float32) / 8388608.0
    elif sampwidth == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise AudioError(f"지원하지 않는 비트 수예요 ({sampwidth * 8}bit)")
    if channels > 1:
        x = x[: (len(x) // channels) * channels].reshape(-1, channels).mean(axis=1)
    return x.astype(np.float32)


def _resample(x, ext0, s0, s1, src_sr, dst_sr):
    """x는 원본 샘플 [ext0, ext0+len(x)) 구간. 원본 [s0, s1)에 해당하는 출력만 돌려준다."""
    if src_sr == dst_sr:
        return x[s0 - ext0: s1 - ext0]
    if src_sr > dst_sr:
        width = int(round(src_sr / dst_sr))
        if width > 1:
            x = np.convolve(x, np.ones(width, dtype=np.float32) / width, mode="same")
    k0 = -((-s0 * dst_sr) // src_sr)       # ceil
    k1 = -((-s1 * dst_sr) // src_sr)
    k = np.arange(k0, k1, dtype=np.float64)
    pos = k * (src_sr / dst_sr) - ext0
    return np.interp(pos, np.arange(len(x)), x).astype(np.float32)


def iter_mono(path, target_sr=C.ANALYSIS_SR, chunk_sec=C.ANALYSIS_CHUNK_SEC):
    """(청크 번호, 총 청크 수, 샘플 배열)을 순서대로 돌려준다."""
    sr, ch, sw, n = wav_info(path)
    chunk = max(1, int(sr * chunk_sec))
    total = max(1, math.ceil(n / chunk))
    try:
        with wave.open(path, "rb") as w:
            for i, s0 in enumerate(range(0, n, chunk)):
                s1 = min(n, s0 + chunk)
                e0 = max(0, s0 - PAD)
                e1 = min(n, s1 + PAD)
                w.setpos(e0)
                x = _to_mono_float(w.readframes(e1 - e0), sw, ch)
                yield i, total, _resample(x, e0, s0, s1, sr, target_sr)
    except (wave.Error, EOFError) as exc:
        raise AudioError(f"wav를 읽는 중 오류가 났어요 ({exc})") from exc

# ============================================================
# 3대역 spectral flux, RMS
# ============================================================

BAND_NAMES = ("low", "mid", "high")
BAND_HZ = ((20, 150), (150, 2000), (2000, 8000))


class FluxExtractor:
    def __init__(self, sr=C.ANALYSIS_SR, frame=C.ANALYSIS_FRAME, hop=C.ANALYSIS_HOP):
        self.sr, self.frame, self.hop = sr, frame, hop
        self.window = np.hanning(frame).astype(np.float32)
        freqs = np.fft.rfftfreq(frame, 1.0 / sr)
        self.bands = [np.where((freqs >= lo) & (freqs < hi))[0] for lo, hi in BAND_HZ]
        self.buf = np.zeros(0, dtype=np.float32)
        self.prev = None
        self._flux = []
        self._rms = []

    def feed(self, samples):
        self.buf = np.concatenate([self.buf, samples.astype(np.float32)])
        if len(self.buf) < self.frame:
            return
        n = (len(self.buf) - self.frame) // self.hop + 1
        idx = np.arange(self.frame)[None, :] + self.hop * np.arange(n)[:, None]
        frames = self.buf[idx]
        spec = np.log1p(np.abs(np.fft.rfft(frames * self.window, axis=1)))
        self._rms.append(np.sqrt(np.mean(frames ** 2, axis=1)))

        prev = spec[:1] if self.prev is None else self.prev[None, :]
        full = np.concatenate([prev, spec], axis=0)
        diff = np.maximum(full[1:] - full[:-1], 0.0)
        if self.prev is None:
            diff[0] = 0.0
        self._flux.append(np.stack([diff[:, b].sum(axis=1) for b in self.bands], axis=1))

        self.prev = spec[-1].copy()
        self.buf = self.buf[n * self.hop:]

    def result(self):
        if not self._flux:
            return np.zeros((0, 3), np.float32), np.zeros(0, np.float32)
        return (np.concatenate(self._flux).astype(np.float32),
                np.concatenate(self._rms).astype(np.float32))

# ============================================================
# onset 검출
# ============================================================

FPS_ANALYSIS = C.ANALYSIS_SR / C.ANALYSIS_HOP

# 대역별 최소 간격(초)
MIN_GAP_SEC = {"low": 0.12, "mid": 0.09, "high": 0.06}


def _moving_mean(x, win):
    win = max(1, win | 1)
    pad = win // 2
    c = np.concatenate([[0.0], np.cumsum(np.pad(x, pad, mode="edge"), dtype=np.float64)])
    return (c[win:] - c[:-win]) / win


def _local_max(x, radius):
    padded = np.pad(x, radius, mode="constant", constant_values=-np.inf)
    view = np.lib.stride_tricks.sliding_window_view(padded, 2 * radius + 1)
    return view.max(axis=1)


def pick_peaks(curve, min_gap_frames):
    """적응형 임계값 + 지역 최대 + 최소 간격(강한 것 우선). (인덱스, 값) 반환."""
    if len(curve) < 3 or float(curve.max()) <= 1e-6:
        return np.zeros(0, np.int64), np.zeros(0, np.float32)
    local = _moving_mean(curve, int(FPS_ANALYSIS * 1.0))
    floor = 0.10 * float(np.percentile(curve, 95))
    thr = local * 1.35 + floor
    is_peak = (curve >= _local_max(curve, 2)) & (curve > thr)
    cand = np.where(is_peak)[0]
    if len(cand) == 0:
        return cand, np.zeros(0, np.float32)

    order = np.lexsort((cand, -curve[cand]))          # 강한 순, 동점은 앞 인덱스
    taken = np.zeros(len(curve), dtype=bool)
    keep = []
    for i in cand[order]:
        lo, hi = max(0, i - min_gap_frames), i + min_gap_frames + 1
        if not taken[lo:hi].any():
            taken[i] = True
            keep.append(i)
    keep = np.array(sorted(keep), dtype=np.int64)
    return keep, curve[keep]


def frame_to_ms(frame):
    """10ms 격자 정수로 변환 (기기 간 부동소수점 차이 방지)."""
    ms = frame * C.ANALYSIS_HOP * 1000.0 / C.ANALYSIS_SR
    return int(np.rint(ms / 10.0)) * 10


def detect_events(flux):
    """flux: (N, 3). 이벤트 목록(시간순)을 돌려준다."""
    events = []
    for b, name in enumerate(BAND_NAMES):
        gap = max(1, int(round(MIN_GAP_SEC[name] * FPS_ANALYSIS)))
        idx, vals = pick_peaks(flux[:, b], gap)
        if len(idx) == 0:
            continue
        ref = float(np.percentile(vals, 95)) or 1.0
        for i, v in zip(idx, vals):
            strength = int(np.clip(np.rint(100.0 * v / ref), 1, 100))
            events.append({"t": frame_to_ms(int(i)), "band": name, "strength": strength})
    order = {n: k for k, n in enumerate(BAND_NAMES)}
    events.sort(key=lambda e: (e["t"], order[e["band"]]))
    return events

# ============================================================
# 구간별 BPM, 정밀 보정, 1/4박 보정
# ============================================================

BPM_MIN, BPM_MAX = 70.0, 180.0


def _autocorr(x):
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    return np.fft.irfft(f * np.conj(f))[:n]


def _segment_bpm(seg):
    """(bpm, confidence). 120 근처를 약하게 선호해 옥타브 오류를 줄인다."""
    seg = seg - seg.mean()
    if len(seg) < int(FPS_ANALYSIS * 6) or float(np.abs(seg).max()) < 1e-6:
        return None, 0.0
    ac = _autocorr(seg)
    if ac[0] <= 0:
        return None, 0.0
    lo = int(60 * FPS_ANALYSIS / BPM_MAX)
    hi = min(len(ac) - 2, int(60 * FPS_ANALYSIS / BPM_MIN))
    if hi <= lo + 2:
        return None, 0.0
    lags = np.arange(lo, hi + 1)
    bpms = 60 * FPS_ANALYSIS / lags
    prior = np.exp(-0.5 * (np.log2(bpms / 120.0) / 1.0) ** 2)
    k = int(np.argmax(ac[lags] * prior))
    lag = int(lags[k])
    a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]            # 포물선 보간
    denom = a - 2 * b + c
    shift = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
    lag_f = lag + float(np.clip(shift, -0.5, 0.5))
    return 60 * FPS_ANALYSIS / lag_f, float(ac[lag] / ac[0])


def _best_phase(curve, period):
    best, best_score = 0.0, -1.0
    for phase in np.arange(0.0, period, 0.5):
        idx = np.rint(np.arange(phase, len(curve), period)).astype(np.int64)
        idx = idx[idx < len(curve)]
        score = float(curve[idx].sum())
        if score > best_score + 1e-9:
            best, best_score = float(phase), score
    return best


def estimate_tempo_map(curve, seg_sec=30, merge_tol=0.03):
    n = len(curve)
    seg = int(seg_sec * FPS_ANALYSIS)
    rows = []                                       # (start_frame, end_frame, bpm, conf)
    for s in range(0, max(n, 1), seg):
        e = min(n, s + seg)
        bpm, conf = _segment_bpm(curve[s:e])
        rows.append((s, e, bpm, conf))

    merged = []
    for s, e, bpm, conf in rows:
        if bpm is None or conf < 0.08:
            if merged:
                merged[-1][1] = e                   # 앞 구간 박자를 이어서 사용
            else:
                merged.append([s, e, 120.0, 0.0, False])
            continue
        if merged and merged[-1][4] and abs(bpm - merged[-1][2]) / merged[-1][2] < merge_tol:
            merged[-1][1] = e
        elif merged and not merged[-1][4]:
            merged[-1] = [merged[-1][0], e, bpm, conf, True]
        else:
            merged.append([s, e, bpm, conf, True])

    tempo_map = []
    for s, e, bpm, conf, found in merged:
        period = 60 * FPS_ANALYSIS / bpm
        phase = _best_phase(curve[s:e], period)
        first = s + phase
        tempo_map.append({
            "fromMs": int(np.rint(s * C.ANALYSIS_HOP * 1000 / C.ANALYSIS_SR / 10)) * 10,
            "bpm": round(float(bpm), 1),
            "offsetMs": int(np.rint(first * C.ANALYSIS_HOP * 1000 / C.ANALYSIS_SR / 10)) * 10,
            "confidence": round(conf, 3),
        })
    if tempo_map:
        tempo_map[0]["fromMs"] = 0
    return tempo_map


def refine_tempo_map(tempo_map, events, duration_ms, span=0.02, step=0.02):
    """검출된 onset들의 위상 일치도(circular coherence)로 BPM과 박자 위치를 정밀 보정한다.

    자기상관은 해상도가 거칠어서 BPM이 0.3% 틀리면 긴 곡에서 격자가 수백 ms 밀린다.
    """
    if not tempo_map or not events:
        return tempo_map
    starts = [m["fromMs"] for m in tempo_map]
    ends = starts[1:] + [duration_ms + 1]
    t_all = np.array([e["t"] for e in events], dtype=np.float64)
    w_all = np.array([e["strength"] * (1.0 if e["band"] != "high" else 0.4)
                      for e in events], dtype=np.float64)
    out = []
    for m, s, e in zip(tempo_map, starts, ends):
        sel = (t_all >= s) & (t_all < e)
        t, w = t_all[sel], w_all[sel]
        if len(t) < 8:
            out.append(m)
            continue
        base = m["bpm"]
        cands = np.arange(base * (1 - span), base * (1 + span) + 1e-9, step)
        best = None
        for bpm in cands:
            period = 60000.0 / bpm
            z = np.sum(w * np.exp(2j * np.pi * (t - s) / period))
            score = abs(z) / w.sum()
            if best is None or score > best[0] + 1e-12:
                best = (score, bpm, period, z)
        _, bpm, period, z = best
        phase = (np.angle(z) / (2 * np.pi)) * period % period       # 구간 시작 기준
        out.append({**m, "bpm": round(float(bpm), 3),
                    "offsetMs": int(np.rint((s + phase) / 10.0)) * 10})
    return out


def snap_events(events, tempo_map, tol=0.35):
    """이벤트를 가까운 1/4박 격자로 보정. 같은 (시간, 대역)이 겹치면 강한 것만 남긴다."""
    if not tempo_map:
        return events
    starts = [m["fromMs"] for m in tempo_map]
    out = {}
    for ev in events:
        m = tempo_map[max(0, bisect.bisect_right(starts, ev["t"]) - 1)]
        grid = 60000.0 / m["bpm"] / 4.0
        k = int(np.rint((ev["t"] - m["offsetMs"]) / grid))
        snapped = m["offsetMs"] + k * grid
        t = ev["t"]
        if abs(ev["t"] - snapped) <= grid * tol and snapped >= 0:
            t = int(np.rint(snapped / 10.0)) * 10
        key = (t, ev["band"])
        if key not in out or ev["strength"] > out[key]["strength"]:
            out[key] = {"t": t, "band": ev["band"], "strength": ev["strength"]}
    order = {"low": 0, "mid": 1, "high": 2}
    return sorted(out.values(), key=lambda e: (e["t"], order[e["band"]]))

# ============================================================
# 강도 구간
# ============================================================



def _mean(x, win):
    win = max(1, win | 1)
    pad = win // 2
    c = np.concatenate([[0.0], np.cumsum(np.pad(x, pad, mode="edge"), dtype=np.float64)])
    return (c[win:] - c[:-win]) / win


def build_sections(rms):
    """[{fromMs, level}] 목록. 1초 단위로 레벨을 정하고 같은 레벨은 합친다."""
    if len(rms) == 0:
        return [{"fromMs": 0, "level": 0}]
    per_sec = int(round(FPS_ANALYSIS))
    smooth = _mean(rms.astype(np.float64), per_sec)
    secs = smooth[::per_sec]
    q = np.percentile(secs, [25, 50, 75])
    level = np.digitize(secs, q).astype(np.float64)       # 0~3
    level = np.rint(_mean(level, 5)).astype(int)           # 짧은 흔들림 제거
    out = []
    for i, lv in enumerate(level):
        if not out or out[-1]["level"] != int(lv):
            out.append({"fromMs": i * 1000, "level": int(lv)})
    return out


def level_at(sections, t_ms):
    starts = [s["fromMs"] for s in sections]
    return sections[max(0, bisect.bisect_right(starts, t_ms) - 1)]["level"]

# ============================================================
# 분석 전체 연결 + 캐시
# ============================================================

def cache_path(song_id, cache_dir=C.CACHE_DIR):
    return os.path.join(cache_dir, f"{song_id}.analysis.json")


def load_cached(song_id, cache_dir=C.CACHE_DIR):
    path = cache_path(song_id, cache_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("analyzerVersion") == C.ANALYZER_VERSION:
            return data
    except (OSError, ValueError):
        pass
    return None


def _save(data, song_id, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    path = cache_path(song_id, cache_dir)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


class _NoCtx:
    cancelled = False
    def report(self, *a, **k): pass
    def check(self): pass


def analyze(ctx, path, cache_dir=C.CACHE_DIR, force=False,
            chunk_sec=C.ANALYSIS_CHUNK_SEC):
    """JobManager 작업 함수. ctx=None이면 그냥 동기 실행."""
    ctx = ctx or _NoCtx()

    ctx.report(0.0, "곡 확인 중")
    song_id = file_sha256(path, ctx, (0.0, 0.08))

    if not force:
        cached = load_cached(song_id, cache_dir)
        if cached:
            ctx.report(1.0, "이미 분석된 곡")
            return cached

    wav, temp = path, None
    if not is_wav(path):
        ctx.report(0.08, "소리 변환 중")
        temp = wav = decode_to_wav(path, ctx)      # ffmpeg 없으면 FfmpegMissing

    try:
        dur = duration_ms(wav)
        fx = FluxExtractor()
        for i, total, samples in iter_mono(wav, chunk_sec=chunk_sec):
            ctx.check()
            fx.feed(samples)
            ctx.report(0.10 + 0.75 * (i + 1) / total, "소리 분석 중")
        flux, rms = fx.result()

        ctx.check()
        ctx.report(0.86, "소리 터지는 지점 찾는 중")
        events = detect_events(flux)

        ctx.report(0.92, "박자 분석 중")
        onset_curve = flux.sum(axis=1)
        tempo_map = estimate_tempo_map(onset_curve)
        tempo_map = refine_tempo_map(tempo_map, events, dur)
        events = snap_events(events, tempo_map)

        ctx.report(0.97, "구간 나누는 중")
        sections = build_sections(rms)
        for ev in events:
            ev["section"] = level_at(sections, ev["t"])
    finally:
        if temp and os.path.exists(temp):
            os.remove(temp)

    result = {
        "songId": song_id,
        "analyzerVersion": C.ANALYZER_VERSION,
        "durationMs": dur,
        "tempoMap": tempo_map,
        "sections": sections,
        "events": events,
    }
    _save(result, song_id, cache_dir)
    ctx.report(1.0, "분석 완료")
    return result

# ============================================================
# 메뉴가 쓰는 창구
# ============================================================

def _key(path):
    return os.path.normcase(os.path.abspath(path))


def friendly_error(job):
    err = job.error or ""
    if "FfmpegMissing" in err:
        return NEEDS_FFMPEG_MSG
    if "AudioError" in err or "ValueError" in err:
        return err.split(": ", 1)[-1]
    return "분석에 실패했어요"


class AnalysisService:

    def __init__(self, workers=1, cache_dir=C.CACHE_DIR):
        self.cache_dir = cache_dir
        self.jobs = JobManager(workers)

    def request(self, path, on_done=None, force=False):
        return self.jobs.submit("분석", analyze, path, self.cache_dir, force,
                                key=_key(path), on_done=on_done)

    def cancel(self, path):
        job = self.jobs.find(_key(path))
        if job and job.active:
            self.jobs.cancel(job)

    def status(self, path):
        """{'state': queued|running|done|failed|cancelled|none, 'progress', 'message'}"""
        job = self.jobs.find(_key(path))
        if job is None:
            return {"state": "none", "progress": 0.0, "message": ""}
        message = friendly_error(job) if job.state == FAILED else job.message
        return {"state": job.state, "progress": job.progress, "message": message}

    def poll(self):
        return self.jobs.poll()

    def shutdown(self):
        self.jobs.shutdown(cancel=True)