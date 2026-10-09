"""App configuration: %APPDATA%/FormatFactory/config.json with defaults."""
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

DEFAULTS = {
    "out_dir": "",
    "conflict": "rename",
    "media_quality": "high",
    "image_quality": "high",
    "soffice_path": "",
    "kit_node": r"C:\Users\ybc12\AppData\Local\Programs\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe",
    "kit_cli": r"C:\Users\ybc12\AppData\Local\Programs\DeepSeek Harness\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js",
}


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "FormatFactory"


def config_path() -> Path:
    return app_data_dir() / "config.json"


@dataclass
class Config:
    out_dir: str = ""
    conflict: str = "rename"
    media_quality: str = "high"
    image_quality: str = "high"
    soffice_path: str = ""
    kit_node: str = ""
    kit_cli: str = ""

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = cls(**DEFAULTS)
            cfg.save()
            return cfg
        known = {f.name for f in fields(cls)}
        merged = {**DEFAULTS, **{k: v for k, v in data.items() if k in known}}
        return cls(**merged)

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, path)
