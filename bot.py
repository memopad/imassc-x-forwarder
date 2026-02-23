import os
import json
import requests
import feedparser
from typing import Optional, Dict, List, Tuple

# ====== 계정별 스레드(포럼 포스트) ID ======
THREAD_IDS = {
    "imassc_official": "1452221967544619101",
    "kadokawa_sk": "1475459223709286410",
}

# ====== 계정별 RSS 소스 후보 ======
SOURCES: Dict[str, List[str]] = {
    "imassc_official": [
        "https://nitter.net/imassc_official/rss",
        "https://xcancel.com/imassc_official/rss",
        "https://nitter.poast.org/imassc_official/rss",
    ],
    "kadokawa_sk": [
        "https://nitter.net/kadokawa_sk/rss",
        "https://xcancel.com/kadokawa_sk/rss",
        "https://nitter.poast.org/kadokawa_sk/rss",
    ],
}

# ====== 계정별 웹훅 env 이름 (너가 말한 것처럼 imassc는 DISCORD_WEBHOOK_URL 유지) ======
WEBHOOK_ENV = {
    "imassc_official": "DISCORD_WEBHOOK_URL",
    "kadokawa_sk": "DISCORD_WEBHOOK_KADOKAWA",
}

STATE_FILE = "state.json"

UA = "Mozilla/5.0 (compatible; x-forwarder/3.0; +https://github.com/)"
ACCEPT = "application/rss+xml, application/xml;q=0.9, */*;q=0.8"


def load_state() -> Dict[str, str]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state: Dict[str, str]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def normalize_to_xdotcom(link: str) -> str:
    link = link.split("#")[0]
    replacements: List[Tuple[str, str]] = [
        ("https://nitter.net/", "https://x.com/"),
        ("https://xcancel.com/", "https://x.com/"),
        ("https://nitter.poast.org/", "https://x.com/"),
        ("http://nitter.net/", "https://x.com/"),
        ("http://xcancel.com/", "https://x.com/"),
        ("http://nitter.poast.org/", "https://x.com/"),
    ]
    for src, dst in replacements:
        if link.startswith(src):
            return link.replace(src, dst, 1)
    return link


def fetch_recent_status_links(url: str, limit: int = 10) -> List[str]:
    r = requests.get(url, headers={"User-Agent": UA, "Accept": ACCEPT}, timeout=20)
    if r.status_code != 200:
        print(f"Fetch failed: {url} -> {r.status_code}")
        return []

    feed = feedparser.parse(r.text)
    links: List[str] = []
    for e in feed.entries[:limit]:
        l = e.get("link")
        if not l:
            continue
        if "/status/" in l:
            links.append(l)
    return links


def post_to_discord_thread(webhook_url: str, thread_id: str, content: str) -> None:
    url = f"{webhook_url}?thread_id={thread_id}"
    resp = requests.post(url, json={"content": content}, timeout=20)
    resp.raise_for_status()


def process_account(account: str, state: Dict[str, str]) -> None:
    thread_id = THREAD_IDS.get(account)
    if not thread_id:
        print(f"[{account}] thread_id missing. Skipping.")
        return

    env_name = WEBHOOK_ENV.get(account)
    webhook = os.getenv(env_name) if env_name else None
    if not webhook:
        print(f"[{account}] webhook env missing ({env_name}). Skipping.")
        return

    latest_link = None
    used_source = None

    recent = []
    for src in SOURCES.get(account, []):
        try:
            links = fetch_recent_status_links(src, limit=10)
            if links:
                # x.com으로 정규화
                recent = [normalize_to_xdotcom(x) for x in links]
                used_source = src
                break
        except Exception as e:
            print(f"[{account}] Error reading {src}: {e}")

    if not recent:
        print(f"[{account}] Could not fetch tweets from any source.")
        return

    last = state.get(account)

    print(f"[{account}] recent[0]:        {recent[0]}")
    print(f"[{account}] last in state:    {last}")
    print(f"[{account}] source:           {used_source}")

    # last가 목록에 있으면, 그 앞(=더 최신) 것들만 전송 대상
    if last in recent:
        idx = recent.index(last)
        to_post = recent[:idx]
    else:
        # state가 없거나(처음) RSS가 리셋되었으면 최신 1개만(스팸 방지)
        to_post = recent[:1]

    # 최신 -> 과거 순으로 되어있으니, 게시할 땐 오래된 것부터 올려 순서 유지
    to_post = list(reversed(to_post))

    if not to_post:
        print(f"[{account}] No new tweet.")
        return

    for link in to_post:
        msg = f"최신 트윗:\n{link}"
        post_to_discord_thread(webhook, thread_id, msg)
        state[account] = link
        print(f"[{account}] Posted: {link}")


def main():
    state = load_state()

    for account in ["imassc_official", "kadokawa_sk"]:
        process_account(account, state)

    # 잔재 키 제거(있어도 되지만 깔끔하게)
    if "last_link" in state:
        del state["last_link"]

    save_state(state)


if __name__ == "__main__":
    main()
