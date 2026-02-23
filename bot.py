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


def fetch_latest_link_from_rss(url: str) -> Optional[str]:
    r = requests.get(url, headers={"User-Agent": UA, "Accept": ACCEPT}, timeout=20)
    if r.status_code != 200:
        print(f"Fetch failed: {url} -> {r.status_code}")
        return None

    feed = feedparser.parse(r.text)
    if not feed.entries:
        print(f"No entries: {url}")
        return None

    # 첫 엔트리가 최신인 게 보통
    link = feed.entries[0].get("link")
    if not link:
        return None

    # 혹시 첫 엔트리가 status가 아니면 status가 나올 때까지 조금 훑음
    if "/status/" not in link:
        for e in feed.entries[:5]:
            l = e.get("link")
            if l and "/status/" in l:
                link = l
                break

    if "/status/" not in link:
        return None

    return link


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

    for src in SOURCES.get(account, []):
        try:
            link = fetch_latest_link_from_rss(src)
            if link:
                latest_link = normalize_to_xdotcom(link)
                used_source = src
                break
        except Exception as e:
            print(f"[{account}] Error reading {src}: {e}")

    if not latest_link:
        print(f"[{account}] Could not fetch latest tweet from any source.")
        return

    # ✅ 디버그 로그: 뭐를 최신이라고 보고 있는지
    print(f"[{account}] latest from rss: {latest_link}")
    print(f"[{account}] last in state:   {state.get(account)}")
    print(f"[{account}] source:          {used_source}")

    if state.get(account) == latest_link:
        print(f"[{account}] No new tweet.")
        return

    msg = f"최신 트윗:\n{latest_link}"
    post_to_discord_thread(webhook, thread_id, msg)

    state[account] = latest_link
    print(f"[{account}] Posted!")


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
