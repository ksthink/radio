"""PiRadio 설정 로더"""

import os
import yaml

_config = None


def load_config(path=None):
    """YAML 설정 파일을 로드한다."""
    global _config
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    return _config


def get_config():
    """현재 설정을 반환한다. 로드되지 않았으면 자동 로드."""
    global _config
    if _config is None:
        load_config()
    return _config
