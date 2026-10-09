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

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = cls()
            cfg.save()
            return cfg
        known = {f.name for f in fields(cls)}
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        return cfg

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, path)
