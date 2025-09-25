from fastapi import FastAPI, HTTPException, APIRouter, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Optional
from data.redis_bus import get_client, publish_json
from utils.notifier import Notifier
import uuid
import json
import os
import random
import threading
import time
import hashlib
import hmac
import secrets

app = FastAPI()
api = APIRouter(prefix="/api")

CMD_CH = "controller:commands"
notifier = Notifier()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginReq(BaseModel):
    email: str

class VerifyReq(BaseModel):
    email: str
    code: str


class GenReq(BaseModel):
    owner: str
    symbol: str


class StartReq(BaseModel):
    owner: str
    symbol: str
    strategy: str = "base"
    fund_amnt: Optional[float] = None

    @field_validator("fund_amnt", mode="before")
    def parse_funds(cls, v):
        if v is None or v == "None" or v == "":
            return None
        else:
            return v

class ListReq(BaseModel):
    owner: str


class AddCoinReq(BaseModel):
    owner: str
    coin: str


class SymbolsResp(BaseModel):
    symbols: list[str]


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _lock_key(email: str) -> str:
    return f"otp_lock:{email}"


def _otp_key(email: str) -> str:
    return f"otp:{email}"


def safe_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def rpc(cmd: dict, timeout=2.0):  # remote procedure call
    r = get_client()
    reply_to = f"controller:replies:{uuid.uuid4().hex}"
    cmd["reply_to"] = reply_to
    publish_json(r, CMD_CH, cmd)
    sub = r.pubsub()
    sub.subscribe(reply_to)
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = sub.get_message(timeout=timeout)
        if msg and msg.get("type") == "message":
            return json.loads(msg["data"])
    raise TimeoutError("no reply")


@api.post("/traders/start")
def start(req: StartReq):
    try:
        response = rpc({"cmd": "start", **req.model_dump()})
        if not response.get("ok"):
            raise HTTPException(400, response)
        return response
    except TimeoutError:
        raise HTTPException(504, "controller did not reply")


@api.post("/traders/stop")
def stop(req: GenReq):
    try:
        response = rpc({"cmd": "stop", **req.model_dump()})
        if not response.get("ok"):
            raise HTTPException(400, response)
        return response
    except TimeoutError:
        raise HTTPException(504, "controller did not reply")


@api.post("/traders/list")
def list(req: ListReq):
    try:
        response = rpc({"cmd": "list", **req.model_dump()})
        if not response.get("ok"):
            raise HTTPException(400, response)
        return response
    except TimeoutError:
        raise HTTPException(504, "controller did not reply")


@api.post("/traders/status")
def status(req: GenReq):
    try:
        response = rpc({"cmd": "status", **req.model_dump()})
        if not response.get("ok"):
            raise HTTPException(400, response)
        return response
    except TimeoutError:
        raise HTTPException(504, "controller did not reply")


@api.post("/traders/add_coin")
def add_coin(req: AddCoinReq):
    try:
        response = rpc({"cmd": "add_coin", **req.model_dump()})
        if not response:
            raise HTTPException(400, response)
        return response
    except TimeoutError:
        raise HTTPException(504, "controller did not reply")


@api.post("/symbols")
def list_symbols():
    symbol_list_path = "/home/halodi/python_scripts/auto-trader/data/symbol_list.json"
    try:
        with open(symbol_list_path, "r") as f:
            symbol_list = json.load(f)
    except FileNotFoundError:
        symbol_list = []
    return {"symbols": symbol_list}


@api.post("/login/send")
def login(req: LoginReq, background_tasks: BackgroundTasks):
    r = get_client()
    email = (req.email).strip().lower()
    key = _otp_key(email)
    if r.exists(_lock_key(email)):
        return {"ok": True}

    otp = f"{random.randint(0, 999999):06d}"
    otp_hash = hash_code(otp)

    payload = json.dumps({"hash": otp_hash, "attempts": 0})
    r.setex(key, 60, payload)
    print(f"[send] key:", key, "exists:", bool(r.exists(_otp_key(email))))

    background_tasks.add_task(
        notifier.send_email,
        "One-Time Code",
        f"Your Z8 login code is {otp}. It expires in 60 seconds.",
        email,
    )
    return {"ok": True}


@api.post("/login/check")
def login_check(req: VerifyReq, response: Response):
    r = get_client()
    email = (req.email).strip().lower()
    key = _otp_key(email)

    if r.exists(_lock_key(email)):
        raise HTTPException(400, "locked")
    blob = r.get(_otp_key(email))
    print("[check] key:", key, "exists:", bool(r.exists(key)))

    if not blob:
        raise HTTPException(400, f"no otp key")

    state = json.loads(blob)
    attempts = int(state.get("attempts", 0))
    if attempts >= 5:
        r.setex(_lock_key(email), 300, "1")
        r.delete(_otp_key(email))
        raise HTTPException(400, "attempts_exceeded")

    provided = hash_code(req.code.strip())
    if not safe_eq(provided, state["hash"]):
        state["attempts"] = attempts + 1
        pipe = r.pipeline()
        pipe.set(_otp_key(email), json.dumps(state))
        pipe.execute()
        raise HTTPException(400, "missing hash/wrong code")

    r.delete(_otp_key(email))

    sid = secrets.token_urlsafe(32)
    session = {"email": email, "owner": email}
    r.setex(f"session:{sid}", 86400, json.dumps(session))

    return {"ok": True}


app.include_router(api)

app.mount("/", StaticFiles(directory="var/www/tradeui", html=True), name="ui")
