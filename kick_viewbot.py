import asyncio
import random
import threading
import time
import os
import sys
import logging
import math
from curl_cffi import requests, AsyncSession
from cachetools import TTLCache
from functools import wraps


# ============================================================================
# CONFIGURATION & GLOBALS
# ============================================================================

target_viewers = 0
current_target = 0
fluctuation_percentage = 0.15
last_major_fluctuation = time.time()
last_minor_fluctuation = time.time()

stats = {"active": 0, "failed": 0, "viewers": 0, "is_live": False}
cache = TTLCache(maxsize=2, ttl=30)
active_connections = {}
fluctuation_lock = threading.Lock()
stream_paused = threading.Event()
stream_paused.clear()

proxies_list = []
log_interval = 10
channel = ""

timeout_workers = []
timeout_ping = []
major_fluctuation_interval = []
minor_fluctuation_interval = []


# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="\033[35m%(asctime)s\033[0m %(message)s",
    datefmt="%m-%d %H:%M",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.info("💥 KICK VIEWER BOT 💥")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def parse_env_list(env_var, default):
    value = os.getenv(env_var)
    if value:
        return [float(x.strip()) for x in value.split(',')]
    return default


def safe_execute(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"❌ Error in {func.__name__}: {str(e)[:100]}")
            return None
    return wrapper


def async_safe_execute(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"❌ Error in {func.__name__}: {str(e)[:100]}")
            return None
    return wrapper


# ============================================================================
# PROXY MANAGEMENT
# ============================================================================

@safe_execute
def load_proxies(file_path="proxies.txt"):
    try:
        with open(file_path, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
        if not proxies:
            logging.error("❌ Missing proxies: \"%s\" is empty.", file_path)
            exit(1)
        logging.info("✅ Loaded %d proxies", len(proxies))
        return proxies
    except FileNotFoundError:
        logging.error("❌ Missing proxies file: %s", file_path)
        exit(1)
    except Exception as e:
        logging.error("❌ Proxy load error: %s", e)
        exit(1)


@safe_execute
def pick_proxy():
    try:
        proxy = random.choice(proxies_list)
        parts = proxy.split(":")
        if len(parts) == 2:
            ip, port = parts
            full_url = f"http://{ip}:{port}"
        elif len(parts) == 4:
            ip, port, user, passwd = parts
            full_url = f"http://{user}:{passwd}@{ip}:{port}"
        else:
            logging.error("❌ Bad proxy format: %s", proxy)
            return None, None
        proxy_dict = {"http": full_url, "https": full_url}
        return proxy_dict, full_url
    except Exception as e:
        logging.error("❌ Proxy error: %s, %s", proxy, str(e)[:50])
        return None, None


# ============================================================================
# KICK API FUNCTIONS
# ============================================================================

@safe_execute
def get_channel_id(channel_name):
    for attempt in range(5):
        try:
            s = requests.Session(impersonate="firefox135")
            proxy_dict, _ = pick_proxy()
            if not proxy_dict:
                continue
            s.proxies = proxy_dict
            
            try:
                r = s.get(f"https://kick.com/api/v2/channels/{channel_name}", timeout=20)
                if r.status_code == 200:
                    channel_id = r.json().get("id")
                    logging.info("✅ Channel ID: %s", channel_id)
                    return channel_id
                elif r.status_code == 404:
                    logging.warning("⚠️ Channel ID not available: %s", r.status_code)
                    exit(1)
            except requests.exceptions.Timeout:
                logging.debug(f"⏱️ Timeout getting channel ID (attempt {attempt + 1}/5)")
            except Exception as e:
                logging.warning("⚠️ Channel ID error: %s, retrying...", str(e)[:50])
            
            time.sleep(random.uniform(0, 1))
        except Exception as e:
            logging.warning(f"⚠️ Loop error in get_channel_id: {str(e)[:50]}")
            time.sleep(random.uniform(0, 1))
    
    logging.error("❌ Failed to get channel ID")
    return None


@safe_execute
def get_viewers_count(channel_name):
    try:
        return cache[channel_name]
    except KeyError:
        pass
    
    for attempt in range(3):
        try:
            s = requests.Session(impersonate="firefox135")
            proxy_dict, _ = pick_proxy()
            if not proxy_dict:
                continue
            s.proxies = proxy_dict
            
            try:
                r = s.get(f"https://kick.com/api/v2/channels/{channel_name}", timeout=20)
                if r.status_code == 200:
                    viewers_count = r.json().get("livestream", {}).get("viewer_count", 0)
                    cache[channel_name] = viewers_count
                    return viewers_count
            except requests.exceptions.Timeout:
                logging.debug(f"⏱️ Timeout getting viewer count (attempt {attempt + 1}/3)")
            except requests.exceptions.RequestException as e:
                logging.debug(f"⚠️ Request error: {str(e)[:50]}")
            except Exception as e:
                logging.debug(f"⚠️ Unexpected error: {str(e)[:50]}")
            
            time.sleep(random.uniform(0, 5))
        except Exception as e:
            logging.debug(f"⚠️ Loop error in get_viewers_count: {str(e)[:50]}")
            continue
    return 0


@safe_execute
def get_stream_alive(channel_name):
    for attempt in range(5):
        try:
            s = requests.Session(impersonate="firefox135")
            proxy_dict, _ = pick_proxy()
            if not proxy_dict:
                continue
            s.proxies = proxy_dict
            
            try:
                r = s.get(f"https://kick.com/api/v2/channels/{channel_name}", timeout=20)
                if r.status_code != 200:
                    logging.warning(f"⚠️ Bad status code: {r.status_code}")
                    continue

                try:
                    data = r.json()
                except ValueError as e:
                    logging.warning(f"⚠️ JSON parse error: {str(e)[:50]}")
                    continue

                livestream = data.get("livestream", None)

                if livestream is None:
                    return False

                if isinstance(livestream, dict):
                    return bool(livestream.get("is_live", False))

                logging.warning("⚠️ Unexpected livestream type: %s", type(livestream))
                return False
                
            except requests.exceptions.Timeout:
                logging.debug(f"⏱️ Timeout checking stream status (attempt {attempt + 1}/5)")
            except requests.exceptions.RequestException as e:
                logging.warning(f"⚠️ Request error: {str(e)[:50]}")
            except Exception as e:
                logging.warning(f"⚠️ Unexpected error: {str(e)[:50]}")

            time.sleep(random.uniform(0, 2))
            
        except Exception as e:
            logging.warning(f"⚠️ Loop error in get_stream_alive: {str(e)[:50]}")
            time.sleep(random.uniform(0, 2))

    logging.error("❌ Failed to check stream status")
    return False


@async_safe_execute
async def get_token_async():
    for attempt in range(5):
        try:
            await asyncio.sleep(random.uniform(0, 2))
            
            try:
                s = requests.Session(impersonate="firefox135")
                proxy_dict, proxy_url = pick_proxy()
                if not proxy_dict:
                    continue
                s.proxies = proxy_dict
                
                try:
                    s.get("https://kick.com", timeout=10)
                    s.headers["X-CLIENT-TOKEN"] = "e1393935a959b4020a4491574f6490129f678acdaa92760471263db43487f823"
                    r = s.get("https://websockets.kick.com/viewer/v1/token", timeout=10)
                    if r.status_code == 200:
                        token = r.json()["data"]["token"]
                        return token, proxy_url
                except requests.exceptions.Timeout:
                    logging.debug(f"⏱️ Token request timeout (attempt {attempt + 1}/5)")
                except Exception as e:
                    logging.debug(f"⚠️ Token request error: {str(e)[:50]}")
            except Exception as e:
                logging.debug(f"⚠️ Session error: {str(e)[:50]}")
            
            await asyncio.sleep(random.uniform(0, 5))
        except Exception as e:
            logging.error(f"❌ Error in token loop: {str(e)[:50]}")
            await asyncio.sleep(1)
    
    return None, None


# ============================================================================
# VIEWER FLUCTUATION LOGIC
# ============================================================================

@safe_execute
def get_bounds():
    try:
        min_viewers = int(target_viewers * (1 - fluctuation_percentage))
        max_viewers = int(target_viewers * (1 + fluctuation_percentage))
        return min_viewers, max_viewers
    except Exception as e:
        logging.error(f"❌ Error calculating bounds: {str(e)[:50]}")
        return 0, 0


@safe_execute
def calculate_realistic_fluctuation(current_count, is_major=False):
    try:
        min_viewers, max_viewers = get_bounds()
        
        distance_from_center = (current_count - target_viewers) / target_viewers if target_viewers > 0 else 0
        center_pull = -distance_from_center * 0.5
        
        if is_major:
            base_change_percent = random.uniform(-fluctuation_percentage * 0.8, fluctuation_percentage * 0.8)
            wave_factor = math.sin(time.time() / 300) * 0.03
            trend = random.choice([-0.02, -0.01, 0, 0.01, 0.02])
            total_change = base_change_percent + wave_factor + trend + center_pull
        else:
            minor_fluctuation = fluctuation_percentage * 0.02
            base_change_percent = random.uniform(-minor_fluctuation, minor_fluctuation)
            jitter = random.uniform(-0.01, 0.01)
            total_change = base_change_percent + jitter + center_pull
        
        new_target = int(current_count * (1 + total_change))
        new_target = max(min_viewers, min(max_viewers, new_target))
        
        return new_target
    except Exception as e:
        logging.error(f"❌ Error in fluctuation calculation: {str(e)[:50]}")
        return current_count


def manage_viewer_fluctuation():
    global last_major_fluctuation, last_minor_fluctuation, current_target
    
    try:
        min_viewers, max_viewers = get_bounds()
        with fluctuation_lock:
            current_target = target_viewers
    except Exception as e:
        logging.error(f"❌ Error initializing fluctuation manager: {str(e)[:50]}")
    
    while True:
        try:
            current_time = time.time()
            
            if stream_paused.is_set():
                try:
                    with fluctuation_lock:
                        old_target = current_target
                        
                        if current_time - last_major_fluctuation > random.uniform(*major_fluctuation_interval):
                            last_major_fluctuation = current_time
                            current_target = calculate_realistic_fluctuation(current_target, is_major=True)
                            
                            change_percent = ((current_target - old_target) / old_target) * 100 if old_target > 0 else 0
                            direction = "📈" if current_target > old_target else "📉"
                            logging.info("%s Major fluctuation: %d → %d viewers (%+.1f%%)", 
                                       direction, old_target, current_target, change_percent)
                        
                        elif current_time - last_minor_fluctuation > random.uniform(*minor_fluctuation_interval):
                            last_minor_fluctuation = current_time
                            current_target = calculate_realistic_fluctuation(current_target, is_major=False)
                            
                            if abs(current_target - old_target) > 0:
                                change_percent = ((current_target - old_target) / old_target) * 100 if old_target > 0 else 0
                                direction = "📈" if current_target > old_target else "📉"
                                logging.info("%s Minor adjustment: %d → %d viewers (%+.1f%%)", 
                                           direction, old_target, current_target, change_percent)
                except Exception as e:
                    logging.error(f"❌ Error in fluctuation logic: {str(e)[:100]}")
                
                try:
                    active_count = len([v for v in active_connections.values() if v])
                    
                    if active_count < current_target:
                        needed = min(current_target - active_count, 5)
                        inactive_ids = [k for k, v in active_connections.items() if not v]
                        for conn_id in inactive_ids[:needed]:
                            active_connections[conn_id] = True
                            time.sleep(random.uniform(0.5, 2))
                    
                    elif active_count > current_target:
                        excess = min(active_count - current_target, 5)
                        active_ids = [k for k, v in active_connections.items() if v]
                        for conn_id in random.sample(active_ids, min(excess, len(active_ids))):
                            active_connections[conn_id] = False
                            time.sleep(random.uniform(0.5, 2))
                except Exception as e:
                    logging.error(f"❌ Error managing connections: {str(e)[:100]}")
            
            time.sleep(10)
        except Exception as e:
            logging.error(f"❌ Critical error in fluctuation manager: {str(e)[:100]}")
            time.sleep(10)


# ============================================================================
# STREAM MONITORING
# ============================================================================

def monitor_stream_status():
    global stats
    check_interval = 20
    logging.info("🟢 Stream monitoring started.")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            try:
                is_live = get_stream_alive(channel)
                stats["is_live"] = is_live
                consecutive_errors = 0
            except Exception as e:
                logging.error(f"❌ Error checking stream status: {str(e)[:100]}")
                consecutive_errors += 1
                is_live = stats.get("is_live", False)
            
            try:
                if not is_live and stream_paused.is_set():
                    stream_paused.clear()
                    logging.info("🔴 Stream is OFFLINE - Pausing all connections")
                    
                    try:
                        for conn_id in active_connections:
                            active_connections[conn_id] = False
                    except Exception as e:
                        logging.error(f"❌ Error pausing connections: {str(e)[:100]}")
                
                elif is_live and not stream_paused.is_set():
                    stream_paused.set()
                    logging.info(f"🟢 Stream is LIVE - Resuming connections")
                    
                    try:
                        active_count = 0
                        sorted_conn_ids = sorted(active_connections.keys())
                        for conn_id in sorted_conn_ids:
                            if active_count < current_target:
                                active_connections[conn_id] = True
                                active_count += 1
                                delay = random.uniform(timeout_workers[0], timeout_workers[1])
                                time.sleep(delay)
                    except Exception as e:
                        logging.error(f"❌ Error resuming connections: {str(e)[:100]}")
            except Exception as e:
                logging.error(f"❌ Error in stream state logic: {str(e)[:100]}")
            
            if consecutive_errors >= max_consecutive_errors:
                logging.error("❌ Too many consecutive errors in stream monitor. Resetting...")
                consecutive_errors = 0
                time.sleep(60)
            else:
                time.sleep(check_interval)
            
        except Exception as e:
            logging.error(f"❌ Critical error in stream monitor: {str(e)[:100]}")
            time.sleep(check_interval)


# ============================================================================
# WEBSOCKET CONNECTION HANDLER
# ============================================================================

def start_connection_thread(channel_id, index):
    global stats, active_connections
    
    async def connection_handler():
        try:
            active_connections[index] = False
        except Exception as e:
            logging.error(f"❌ [{index:03d}] Error initializing connection: {str(e)[:50]}")
        
        while True:
            try:
                try:
                    while not stream_paused.is_set():
                        await asyncio.sleep(5)
                except Exception as e:
                    logging.error(f"❌ [{index:03d}] Error in pause wait: {str(e)[:50]}")
                    await asyncio.sleep(5)
                    continue
                
                try:
                    while not active_connections.get(index, False):
                        await asyncio.sleep(random.uniform(1, 5))
                        if not stream_paused.is_set():
                            break
                        continue
                except Exception as e:
                    logging.error(f"❌ [{index:03d}] Error in activation wait: {str(e)[:50]}")
                    await asyncio.sleep(5)
                    continue
                
                if not stream_paused.is_set():
                    continue
                
                try:
                    token, proxy_url = await get_token_async()
                    if not token:
                        logging.warning("⚠️ [%03d] Failed to get token, retrying...", index)
                        await asyncio.sleep(5)
                        continue
                except Exception as e:
                    logging.error(f"❌ [{index:03d}] Token error: {str(e)[:50]}")
                    await asyncio.sleep(5)
                    continue
                
                try:
                    async with AsyncSession() as session:
                        try:
                            ws = await asyncio.wait_for(
                                session.ws_connect(
                                    f"wss://websockets.kick.com/viewer/v1/connect?token={token}",
                                    proxy=proxy_url,
                                ),
                                timeout=15,
                            )
                        except asyncio.TimeoutError:
                            logging.debug("⏱️ [%03d] WebSocket connection timeout", index)
                            stats["failed"] += 1
                            await asyncio.sleep(random.uniform(5, 10))
                            continue
                        except Exception as e:
                            logging.debug(f"❌ [{index:03d}] WS connect error: {str(e)[:50]}")
                            stats["failed"] += 1
                            await asyncio.sleep(random.uniform(5, 10))
                            continue
                        
                        try:
                            stats["active"] += 1
                            counter = 0
                            
                            try:
                                while True:
                                    try:
                                        if not stream_paused.is_set():
                                            logging.debug("🔴 [%03d] Stream offline, closing connection", index)
                                            break
                                        
                                        if not active_connections.get(index, False):
                                            logging.debug("🔄 [%03d] Connection deactivated by manager", index)
                                            break
                                    except Exception as e:
                                        logging.error(f"❌ [{index:03d}] State check error: {str(e)[:50]}")
                                        break
                                    
                                    counter += 1
                                    
                                    try:
                                        if counter % 2 == 0:
                                            await asyncio.wait_for(
                                                ws.send_json({"type": "ping"}),
                                                timeout=10
                                            )
                                        else:
                                            await asyncio.wait_for(
                                                ws.send_json({
                                                    "type": "channel_handshake",
                                                    "data": {"message": {"channelId": channel_id}}
                                                }),
                                                timeout=10
                                            )
                                    except asyncio.TimeoutError:
                                        logging.debug("⏱️ [%03d] WebSocket send timeout", index)
                                        break
                                    except Exception as send_err:
                                        logging.debug("❌ [%03d] Send error: %s", index, str(send_err)[:30])
                                        break
                                    
                                    try:
                                        if counter % 2 == 0:
                                            stats["viewers"] = get_viewers_count(channel)
                                    except Exception as e:
                                        logging.debug(f"❌ [{index:03d}] Viewer count error: {str(e)[:50]}")
                                    
                                    base_delay = random.uniform(timeout_ping[0], timeout_ping[1])
                                    jitter = random.uniform(-0.5, 0.5)
                                    await asyncio.sleep(max(1, base_delay + jitter))
                                    
                            except Exception as e:
                                logging.error(f"❌ [{index:03d}] Message loop error: {str(e)[:100]}")
                        finally:
                            try:
                                stats["active"] = max(0, stats["active"] - 1)
                            except Exception:
                                pass
                            
                            try:
                                await ws.close()
                            except Exception:
                                pass
                            
                            try:
                                await asyncio.sleep(random.uniform(5, 15))
                            except Exception:
                                pass
                            
                except Exception as e:
                    try:
                        stats["failed"] += 1
                    except Exception:
                        pass
                    logging.debug("❌ [%03d] Connection error: %s", index, str(e)[:50])
                    try:
                        await asyncio.sleep(random.uniform(5, 10))
                    except Exception:
                        pass
                    
            except Exception as e:
                logging.error("❌ [%03d] Handler error: %s", index, str(e)[:100])
                try:
                    await asyncio.sleep(10)
                except Exception:
                    time.sleep(10)
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(False)
        
        try:
            loop.run_until_complete(connection_handler())
        except KeyboardInterrupt:
            logging.info("[%03d] Thread interrupted", index)
        except Exception as e:
            logging.error("❌ [%03d] Loop run error: %s", index, str(e)[:100])
    except Exception as e:
        logging.error("❌ [%03d] Loop creation error: %s", index, str(e)[:100])
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        except Exception as cleanup_err:
            logging.debug("[%03d] Cleanup error: %s", index, str(cleanup_err)[:50])


# ============================================================================
# STATUS LOGGING
# ============================================================================

def log_status():
    global stats, log_interval
    
    last_message = None
    
    while True:
        try:
            try:
                active = [k for k, v in active_connections.items() if v]
                inactive = [k for k, v in active_connections.items() if not v]
                total = len(active_connections)
            except Exception as e:
                logging.error(f"❌ Error counting active connections: {str(e)[:50]}")
                active = 0
                inactive = 0
                total = 0
            
            try:
                min_viewers, max_viewers = get_bounds()
            except Exception as e:
                logging.error(f"❌ Error getting bounds: {str(e)[:50]}")
                min_viewers, max_viewers = 0, 0
            
            try:
                current_message = (
                    f"👁️  Watching: {stats['active']} | "
                    f"🎯 Target viewers: {current_target} | "
                    f"📊 Viewers range: [{min_viewers}-{max_viewers}] | "
                    f"❌ Failed: {stats['failed']} | "
                    f"👥 Viewers: {stats['viewers']} | "
                    f"🟢 Live running? : {stats['is_live']} | "
                    f"⚡ Threads: {len(active)} Active/ {len(inactive)} InActive/ {total} Total"
                )
                if current_message != last_message:
                    logging.info(current_message)
                    last_message = current_message
            except Exception as e:
                logging.error(f"❌ Error creating log message: {str(e)[:50]}")
            
            time.sleep(log_interval)
        except Exception as e:
            logging.error("❌ Log status error: %s", str(e)[:100])
            try:
                time.sleep(log_interval)
            except Exception:
                time.sleep(10)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    try:
        timeout_workers = parse_env_list('TIMEOUT_WORKERS', [10, 120])
        timeout_ping = parse_env_list('TIMEOUT_PING', [2, 12])
        major_fluctuation_interval = parse_env_list('MAJOR_FLUCTUATION_INTERVAL', [60*3, 60*10])
        minor_fluctuation_interval = parse_env_list('MINOR_FLUCTUATION_INTERVAL', [60*1, 60*3])
        
        log_interval = int(os.getenv("LOG_INTERVAL", 10))
        fluctuation_percentage = float(os.getenv("FLUCTUATION_PERCENT", fluctuation_percentage))
        
        logging.info("📊 Fluctuation set to ±%.0f%%", fluctuation_percentage * 100)
        logging.info("⏰ Worker timeout: %s", timeout_workers)
        logging.info("🏓 Ping timeout: %s", timeout_ping)
        
        channel = os.getenv("CHANNEL")
        if not channel:
            channel = str(input("Channel name: ").split("/")[-1])
        
        spawn_viewers = os.getenv("SPAWN_VIEWERS")
        if not spawn_viewers:
            spawn_viewers = int(input("Target viewers: "))
        else:
            spawn_viewers = int(spawn_viewers)
        
        target_viewers = spawn_viewers
        current_target = spawn_viewers
        
        proxies_list = load_proxies()
        
        channel_id = get_channel_id(channel)
        if not channel_id:
            logging.error("❌ Channel not found.")
            exit(1)
        
        min_v, max_v = get_bounds()
        logging.info("🚀 Starting %d viewers for \"%s\" with ±%.0f%% fluctuations (Range: %d-%d)",
                     spawn_viewers, channel, fluctuation_percentage * 100, min_v, max_v)
        
        stats["viewers"] = get_viewers_count(channel)
        
        threading.Thread(target=log_status, daemon=True).start()
        threading.Thread(target=manage_viewer_fluctuation, daemon=True).start()
        threading.Thread(target=monitor_stream_status, daemon=True).start()
        
        min_viewers, max_viewers = get_bounds()
        threads = []
        for i in range(max_viewers):
            try:
                t = threading.Thread(target=start_connection_thread, args=(channel_id, i))
                t.daemon = False
                threads.append(t)
                t.start()
                time.sleep(random.uniform(timeout_workers[0], timeout_workers[1]))
            except Exception as e:
                logging.error(f"❌ Error starting thread {i}: {str(e)[:100]}")
        
        logging.info("✅ All workers spawned. Running forever...")
        
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logging.info("\n🛑 Keyboard interrupt received. Exiting...")
            sys.exit(0)
            
    except Exception as e:
        logging.error(f"❌ Critical error in main: {str(e)[:200]}")
        sys.exit(1)
