import os

from box_sdk_gen import BoxCCGAuth, BoxClient, CCGConfig
from dotenv import load_dotenv

load_dotenv()


def get_box_client() -> BoxClient:
    config = CCGConfig(
        client_id=os.getenv("BOX_CLIENT_ID"),
        client_secret=os.getenv("BOX_CLIENT_SECRET"),
        user_id=(os.getenv("BOX_USER_ID") or "").strip(),
    )
    return BoxClient(auth=BoxCCGAuth(config=config))
