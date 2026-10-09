"""Config module tests (Task 3)."""
import json

from app import config as cfg


def test_app_data_dir_uses_apdata_env(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert cfg.app_data_dir() == tmp_path / "FormatFactory"


def test_load_missing_returns_defaults_and_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    c = cfg.Config.load()
    assert c.conflict == "rename"
    assert c.media_quality == "high"
    assert c.image_quality == "high"
    assert c.out_dir == ""
    assert c.soffice_path == ""
    assert c.kit_node != "" and c.kit_cli != ""
    assert (tmp_path / "FormatFactory" / "config.json").exists()


def test_load_bad_json_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    d = tmp_path / "FormatFactory"
    d.mkdir(parents=True)
    (d / "config.json").write_text("{not json", encoding="utf-8")
    c = cfg.Config.load()
    assert c.conflict == "rename"


def test_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    c = cfg.Config(conflict="skip", media_quality="low", image_quality="low",
                   out_dir=str(tmp_path / "out"), soffice_path=r"C:\soffice\soffice.exe")
    c.save()
    loaded = cfg.Config.load()
    assert loaded.conflict == "skip"
    assert loaded.media_quality == "low"
    assert loaded.image_quality == "low"
    assert loaded.out_dir == str(tmp_path / "out")
    assert loaded.soffice_path == r"C:\soffice\soffice.exe"
    # 文件是合法 JSON 且为 UTF-8
    text = (tmp_path / "FormatFactory" / "config.json").read_text(encoding="utf-8")
    assert json.loads(text)["conflict"] == "skip"
