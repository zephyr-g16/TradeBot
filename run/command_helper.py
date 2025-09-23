from data.redis_bus import get_client
import time
import json

HB_EVERY = 60

CMD_CH = "controller:commands"
RPL_CH = "controller:replies"
HB_KEY= "heartbeat:traders:last"


def send_cmd(cmd: dict, wait_reply=True, timeout=2.0) -> dict | None:
    r = get_client()
    ps = None
    try:
        if wait_reply:
            ps = r.pubsub()
            ps.subscribe(RPL_CH)
        r.publish(CMD_CH, json.dumps(cmd))
        if not wait_reply:
            return None
        end = time.time() + timeout
        while time.time() < end:
            msg = ps.get_message(timeout=0.2)
            if not msg or msg.get("type") != "message":
                continue
            payload = msg['data']
            if isinstance(payload, (bytes, bytearray)):
                payload = payload.decode()
            return json.loads(payload)
    finally:
        if ps:
            try:
                ps.unsubscribe(RPL_CH)
            except: pass
            ps.close()

def get_heartbeat() -> dict | None:
    r = get_client()
    raw = r.get(HB_KEY)
    if not raw:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    try:
        return json.loads(raw)
    except Exception:
        return None