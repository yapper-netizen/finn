"""India time helper: NSE timestamps are IST, but the server may run in UTC."""
from datetime import datetime, timedelta, timezone

import config

IST = timezone(timedelta(hours=config.IST_OFFSET_HOURS))


def ist_now() -> datetime:
    """Current India time as a naive datetime (comparable with filing timestamps)."""
    return datetime.now(IST).replace(tzinfo=None)
