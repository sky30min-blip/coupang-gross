# config 패키지: 상위 폴더의 config.py(API 키)를 불러와 재내보냄
# config.py 파일과 config/ 폴더가 같이 있으면 Python이 이 패키지를 먼저 로드하므로
# 여기서 config.py 내용을 불러와 사용하도록 함

import importlib.util
from pathlib import Path

_config_py = Path(__file__).resolve().parent.parent / "config.py"
if _config_py.exists():
    _spec = importlib.util.spec_from_file_location("_api_config", _config_py)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    CUSTOMER_ID = getattr(_mod, "CUSTOMER_ID", "")
    SECRET_KEY = getattr(_mod, "SECRET_KEY", "")
    ACCESS_LICENSE = getattr(_mod, "ACCESS_LICENSE", "")
    NAVER_CLIENT_ID = getattr(_mod, "NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = getattr(_mod, "NAVER_CLIENT_SECRET", "")
    COUPANG_ACCESS_KEY = getattr(_mod, "COUPANG_ACCESS_KEY", "")
    COUPANG_SECRET_KEY = getattr(_mod, "COUPANG_SECRET_KEY", "")
    COUPANG_USER_AGENT = getattr(_mod, "COUPANG_USER_AGENT", "")
    DOEMEGGOOK_ID = getattr(_mod, "DOEMEGGOOK_ID", "")
    DOEMEGGOOK_PW = getattr(_mod, "DOEMEGGOOK_PW", "")
    OWNERCLAN_ID = getattr(_mod, "OWNERCLAN_ID", "")
    OWNERCLAN_PW = getattr(_mod, "OWNERCLAN_PW", "")
    COUPANG_FEE_RATE = getattr(_mod, "COUPANG_FEE_RATE", 0.11)
    SHIPPING_COST = getattr(_mod, "SHIPPING_COST", 3000)
    VAT_RATE = getattr(_mod, "VAT_RATE", 0.10)
    TARGET_NET_MARGIN = getattr(_mod, "TARGET_NET_MARGIN", 0.15)
else:
    CUSTOMER_ID = ""
    SECRET_KEY = ""
    ACCESS_LICENSE = ""
    NAVER_CLIENT_ID = ""
    NAVER_CLIENT_SECRET = ""
    COUPANG_ACCESS_KEY = ""
    COUPANG_SECRET_KEY = ""
    COUPANG_USER_AGENT = ""
    DOEMEGGOOK_ID = ""
    DOEMEGGOOK_PW = ""
    OWNERCLAN_ID = ""
    OWNERCLAN_PW = ""
    COUPANG_FEE_RATE = 0.11
    SHIPPING_COST = 3000
    VAT_RATE = 0.10
    TARGET_NET_MARGIN = 0.15
