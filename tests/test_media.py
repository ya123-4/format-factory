"""Media argument builder and copy-compatibility matrix tests (Task 8)."""
from app.config import Config
from app.engine import media
from app.engine.media import MediaEngine, MediaMeta, build_media_args, copy_compatible


def _video_meta(codec="h264", has_audio=True):
    return MediaMeta(kind="video", codec=codec, container="mp4", has_audio=has_audio)


def _audio_meta(codec="flac"):
    return MediaMeta(kind="audio", codec=codec, container="flac", has_audio=True)


def test_build_args_copy():
    args = build_media_args("a.mp4", "b.mkv", _video_meta(), "high", copy_ok=True)
    assert "-y" in args and "-nostats" in args
    i = args.index("-c")
    assert args[i + 1] == "copy"
    assert args[-1] == "b.mkv"


def test_build_args_video_crf_quality():
    for quality, crf in (("high", "18"), ("medium", "23"), ("low", "28")):
        args = build_media_args("a.mp4", "b.mp4", _video_meta(), quality, copy_ok=False)
        i = args.index("-crf")
        assert args[i + 1] == crf
        assert "-c:v" in args and args[args.index("-c:v") + 1] == "libx264"


def test_build_args_audio_bitrate():
    for quality, br in (("high", "192k"), ("medium", "128k"), ("low", "96k")):
        args = build_media_args("a.flac", "b.mp3", _audio_meta(), quality, copy_ok=False)
        i = args.index("-b:a")
        assert args[i + 1] == br
        assert args[args.index("-c:a") + 1] == "libmp3lame"


def test_build_args_ogg_uses_libopus():
    args = build_media_args("a.flac", "b.ogg", _audio_meta(), "high", copy_ok=False)
    assert args[args.index("-c:a") + 1] == "libopus"


def test_build_args_gif_special():
    args = build_media_args("a.mp4", "b.gif", _video_meta(), "high", copy_ok=False)
    i = args.index("-vf")
    assert args[i + 1] == "fps=10,scale=320:-1"


def test_build_args_webm_uses_vp9():
    args = build_media_args("a.mp4", "b.webm", _video_meta(), "high", copy_ok=False)
    i = args.index("-c:v")
    assert args[i + 1] == "libvpx-vp9"


def test_matrix_known_compatible():
    assert copy_compatible(_video_meta("h264"), "mkv") is True
    assert copy_compatible(_audio_meta("aac"), "mp4") is True


def test_matrix_unknown_combo_false():
    assert copy_compatible(_video_meta("h264"), "gif") is False
    assert copy_compatible(_video_meta("prores"), "mkv") is False  # 矩阵外编码


def test_copy_compatible_unknown_codec_returns_none():
    assert copy_compatible(_video_meta(""), "mp4") is None
    assert copy_compatible(_video_meta("unknown"), "mp4") is None
    # 矩阵外但非空的编码名 → False（降级重编码），不是 None
    assert copy_compatible(_video_meta("vdat-x"), "mp4") is False


class _FakeRun:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, dst, stop_event):
        self.calls.append((cmd, dst, stop_event))


class _FakeProber:
    def __init__(self, meta):
        self._meta = meta

    def probe(self, path):
        return self._meta


def _engine(meta, run):
    return MediaEngine(
        ffmpeg_path="ff.exe",
        ffprobe_path="fp.exe",
        config=Config(),
        stop_event=None,
        prober=_FakeProber(meta),
        run=run,
    )


def _job(target_fmt):
    from app.engine.models import ConversionJob

    j = ConversionJob(src_path="a.mp4", out_dir="out", target_fmt=target_fmt)
    j.final_path = f"out/b.{target_fmt}"
    return j


def test_engine_copy_decision():
    run = _FakeRun()
    eng = _engine(_video_meta("h264"), run)
    eng.convert(_job("mkv"))
    cmd = run.calls[0][0]
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"


def test_engine_downscale_incompatible():
    run = _FakeRun()
    eng = _engine(_video_meta("h264"), run)
    note = eng.convert(_job("gif"))
    cmd = run.calls[0][0]
    assert not ("-c" in cmd and cmd[cmd.index("-c") + 1] == "copy")
    assert "已降级重编码" in note
    assert "h264" in note and "gif" in note


def test_engine_unknown_codec_downscale():
    run = _FakeRun()
    eng = _engine(_video_meta(""), run)
    note = eng.convert(_job("mp4"))
    cmd = run.calls[0][0]
    assert not ("-c" in cmd and cmd[cmd.index("-c") + 1] == "copy")
    assert "源编码未知，已按高质量重编码" in note
