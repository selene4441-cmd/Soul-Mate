import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import get_settings
from app.database import ensure_schema, make_engine, make_session_factory
from app.service import refresh_all
from app.tikhub import TikhubClient


def main() -> int:
    parser = argparse.ArgumentParser(description="小红书客户数据增量刷新（可交给计划任务/cron 调用）")
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="单次请求间隔秒数，默认读取 .env 中的 REQUEST_INTERVAL_SECONDS",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(settings.database_url)
    ensure_schema(engine)
    session_factory = make_session_factory(engine)
    client = TikhubClient(settings)
    interval = args.interval if args.interval is not None else settings.request_interval_seconds

    try:
        with session_factory() as db:
            summary = refresh_all(db, client, interval=interval)
        print(summary)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())