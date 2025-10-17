import os
import json
import time
import asyncio
from typing import Optional, Dict, Any, List

# 可选指标支持
try:
    from prometheus_client import Counter
    _PROM_ENABLED = True
except Exception:
    _PROM_ENABLED = False
    Counter = None  # type: ignore

try:
    from redis.asyncio import Redis
except Exception:
    Redis = None  # type: ignore

_redis: Optional["Redis"] = None
_memory_pdf_files: Dict[str, Dict[str, Any]] = {}
_memory_citations: Dict[str, Dict[str, Any]] = {}
_memory_sessions: Dict[str, List[Dict[str, Any]]] = {}
_memory_pdf_expire: Dict[str, float] = {}
_memory_cit_expire: Dict[str, float] = {}
_memory_sess_expire: Dict[str, float] = {}

# TTL 配置（秒）
PDF_STATE_TTL_SEC = int(os.getenv("PDF_STATE_TTL_SECONDS", "86400"))  # 1 天
CITATION_TTL_SEC = int(os.getenv("CITATION_TTL_SECONDS", "259200"))    # 3 天
SESSION_TTL_SEC = int(os.getenv("SESSION_TTL_SECONDS", "604800"))      # 7 天

# 会话裁剪与单条长度限制
SESSION_MAX_MESSAGES = int(os.getenv("SESSION_MAX_MESSAGES", "100"))
SESSION_MAX_MSG_CHARS = int(os.getenv("SESSION_MAX_MSG_CHARS", "4000"))

# 重试配置
REDIS_MAX_RETRIES = int(os.getenv("STATE_REDIS_MAX_RETRIES", "3"))
REDIS_RETRY_BASE_MS = int(os.getenv("STATE_REDIS_RETRY_BASE_MS", "50"))

# 指标：会话操作
if _PROM_ENABLED:
    SESSION_APPEND_TOTAL = Counter(
        "session_append_total", "Total session append operations", ["backend"]
    )
    SESSION_TRIM_TOTAL = Counter(
        "session_trim_total", "Total session trim operations", ["backend"]
    )
    SESSION_READ_TOTAL = Counter(
        "session_read_total", "Total session read operations", ["backend"]
    )
    SESSION_CLEAR_TOTAL = Counter(
        "session_clear_total", "Total session clear operations", ["backend"]
    )
    SESSION_FALLBACK_TOTAL = Counter(
        "session_fallback_total", "Total session fallbacks to memory", ["reason"]
    )

async def _init_redis() -> Optional["Redis"]:
    global _redis, Redis
    if _redis is not None:
        return _redis
    # 动态重载 redis.asyncio，当模块在进程启动后才安装时允许后续连接
    if Redis is None:
        try:
            from redis.asyncio import Redis as RedisClient  # type: ignore
            Redis = RedisClient  # type: ignore
        except Exception:
            return None
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        _redis = Redis.from_url(url, decode_responses=True)
        # 验证连接
        await _redis.ping()
        print(f"[STATE] Connected to Redis: {url}")
        return _redis
    except Exception as e:
        _redis = None
        print(f"[STATE] Redis unavailable, fallback to memory: {e}")
        return None

async def _retry_redis(op, *args, **kwargs):
    """带指数退避的简易重试封装（仅在 Redis 可用时调用）。"""
    last_err = None
    for attempt in range(REDIS_MAX_RETRIES):
        try:
            return await op(*args, **kwargs)
        except Exception as e:
            last_err = e
            delay = (REDIS_RETRY_BASE_MS / 1000.0) * (2 ** attempt)
            await asyncio.sleep(delay)
    # 最后一次失败抛出
    raise last_err

# ---------------- PDF Files State ----------------

async def set_pdf_state(file_id: str, state: Dict[str, Any]) -> bool:
    r = await _init_redis()
    if r:
        await _retry_redis(r.set, f"pdf:{file_id}", json.dumps(state), ex=PDF_STATE_TTL_SEC)
    else:
        _memory_pdf_files[file_id] = state
        _memory_pdf_expire[file_id] = time.time() + PDF_STATE_TTL_SEC
    return True

async def get_pdf_state(file_id: str) -> Optional[Dict[str, Any]]:
    r = await _init_redis()
    if r:
        data = await _retry_redis(r.get, f"pdf:{file_id}")
        return json.loads(data) if data else None
    # 内存回退带 TTL
    exp = _memory_pdf_expire.get(file_id)
    if exp and exp < time.time():
        _memory_pdf_files.pop(file_id, None)
        _memory_pdf_expire.pop(file_id, None)
        return None
    return _memory_pdf_files.get(file_id)

async def update_pdf_state(file_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    current = await get_pdf_state(file_id) or {}
    current.update(patch)
    await set_pdf_state(file_id, current)
    return current

# ---------------- Citations ----------------

async def set_citation(citation_id: str, data: Dict[str, Any]) -> bool:
    r = await _init_redis()
    if r:
        await _retry_redis(r.set, f"cit:{citation_id}", json.dumps(data), ex=CITATION_TTL_SEC)
    else:
        _memory_citations[citation_id] = data
        _memory_cit_expire[citation_id] = time.time() + CITATION_TTL_SEC
    return True

async def get_citation(citation_id: str) -> Optional[Dict[str, Any]]:
    r = await _init_redis()
    if r:
        data = await _retry_redis(r.get, f"cit:{citation_id}")
        return json.loads(data) if data else None
    exp = _memory_cit_expire.get(citation_id)
    if exp and exp < time.time():
        _memory_citations.pop(citation_id, None)
        _memory_cit_expire.pop(citation_id, None)
        return None
    return _memory_citations.get(citation_id)

# ---------------- Sessions ----------------

async def get_session_history(session_id: str) -> List[Dict[str, Any]]:
    r = await _init_redis()
    key = f"sess:{session_id}"
    if r:
        # 使用 Redis 列表存储，每个元素为一条消息的 JSON
        try:
            items = await _retry_redis(r.lrange, key, 0, -1)
        except Exception:
            items = []
        hist: List[Dict[str, Any]] = []
        for it in items:
            try:
                obj = json.loads(it)
                if isinstance(obj, dict):
                    role = obj.get("role")
                    content = obj.get("content")
                    if isinstance(role, str) and isinstance(content, str):
                        hist.append({"role": role, "content": content})
            except Exception:
                # 忽略坏数据条目
                continue
        if _PROM_ENABLED:
            SESSION_READ_TOTAL.labels("redis").inc()
        return hist
    # 内存回退带 TTL
    exp = _memory_sess_expire.get(session_id)
    if exp and exp < time.time():
        _memory_sessions.pop(session_id, None)
        _memory_sess_expire.pop(session_id, None)
        if _PROM_ENABLED:
            SESSION_READ_TOTAL.labels("memory").inc()
        return []
    if _PROM_ENABLED:
        SESSION_READ_TOTAL.labels("memory").inc()
    return _memory_sessions.get(session_id, [])

async def append_session_history(session_id: str, role: str, content: str) -> None:
    # 规范化与裁剪
    msg_role = role
    msg_content = content if isinstance(content, str) else str(content)
    if SESSION_MAX_MSG_CHARS > 0 and isinstance(msg_content, str):
        msg_content = msg_content[:SESSION_MAX_MSG_CHARS]

    item_json = json.dumps({"role": msg_role, "content": msg_content}, ensure_ascii=False)

    r = await _init_redis()
    key = f"sess:{session_id}"
    if r:
        # 原子性：RPUSH + LTRIM + EXPIRE
        async def _pipe_exec():
            p = r.pipeline(transaction=True)
            p.rpush(key, item_json)
            # 保留最新 N 条（如果 N<=0 则不裁剪）
            if SESSION_MAX_MESSAGES > 0:
                p.ltrim(key, -SESSION_MAX_MESSAGES, -1)
            p.expire(key, SESSION_TTL_SEC)
            return await p.execute()

        await _retry_redis(_pipe_exec)
        if _PROM_ENABLED:
            SESSION_APPEND_TOTAL.labels("redis").inc()
            if SESSION_MAX_MESSAGES > 0:
                SESSION_TRIM_TOTAL.labels("redis").inc()
        return
    # 内存回退
    if _PROM_ENABLED:
        SESSION_FALLBACK_TOTAL.labels("redis_unavailable").inc()
    history = _memory_sessions.get(session_id, [])
    history.append({"role": msg_role, "content": msg_content})
    if SESSION_MAX_MESSAGES > 0:
        history = history[-SESSION_MAX_MESSAGES:]
    _memory_sessions[session_id] = history
    _memory_sess_expire[session_id] = time.time() + SESSION_TTL_SEC
    if _PROM_ENABLED:
        SESSION_APPEND_TOTAL.labels("memory").inc()
        if SESSION_MAX_MESSAGES > 0:
            SESSION_TRIM_TOTAL.labels("memory").inc()

async def clear_session_history(session_id: str) -> None:
    r = await _init_redis()
    key = f"sess:{session_id}"
    if r:
        try:
            await _retry_redis(r.delete, key)
            if _PROM_ENABLED:
                SESSION_CLEAR_TOTAL.labels("redis").inc()
        except Exception:
            # 失败不阻断内存清理
            pass
    else:
        if _PROM_ENABLED:
            SESSION_CLEAR_TOTAL.labels("memory").inc()
    _memory_sessions.pop(session_id, None)
    _memory_sess_expire.pop(session_id, None)

# ---------------- Health ----------------

async def redis_health() -> Dict[str, Any]:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = await _init_redis()
    if r:
        try:
            start = time.perf_counter()
            await _retry_redis(r.ping)
            latency = time.perf_counter() - start
            return {"connected": True, "url": url, "latency_ms": int(latency * 1000), "mode": "redis"}
        except Exception as e:
            return {"connected": False, "url": url, "error": str(e), "mode": "redis"}
    return {"connected": False, "url": url, "mode": "memory"}