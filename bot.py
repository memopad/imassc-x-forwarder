import os
import json
import requests
from typing import Optional, Dict, List, Tuple

# =========================
# 1) 계정별 "스레드(포럼 포스트) ID"를 여기 채우기
#    - 너가 준 링크에서 /channels/서버ID/스레드ID 이 중 '스레드ID'가 thread_id임
# =========================
THREAD_IDS = {
    "imassc_official": "1452221967544619101",   # <- 여기 (이미 알고 있는 값)
    "kadokawa_sk":     "1475459357847322635",  # <- 여기에 kadokawa용 스레드ID 넣기
}

# =========================
# 2) 계정별 RSS 소스 후보들
#    (인스턴스마다 막히는 게 달라서 여러 개 둠)
# =========================
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

# =========================
# 3) 계정별 웹훅 (GitHub Secrets)
# =========================
WEBHOOKS = {
    "imassc_official": os.environ["DISCORD_WEBHOOK_IMASSC"],
    "kadokawa_sk": os.environ["DISCORD_WEBHOOK_KADOKAWA"],
}

# =========================
# 4) 중복 방지 상태 파일
#    계정별 last_link 저장
# =========================
STATE_FILE = "state.json"

UA = "Mozilla/5.0 (compatible; x-forwarder/2.0; +https://github.com/)"
ACCEPT = "application/rss+xml, application/xml;q=0.9, */*;q=0.8"


def load_state() -> Dict[str, str]:
    """
    state.json 예시:
    {
      "imassc_official": "https://x.com/.../status/...",
      "kadokawa_sk": "https://x.com/.../status/..."
    }
    """
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state: Dict[str, str]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def fetch_latest_link_from_rss(url: str) -> Optional[str]:
    r = requests.get(
        url,
        headers={"User-Agent": UA, "Accept": ACCEPT},
        timeout=20,
    )
    if r.status_code != 200:
        print(f"Fetch failed: {url} -> {r.status_code}")
        return None

    text = r.text

    # 단순 파싱: <link>...</link> 중 /status/ 포함 링크 찾기
    start = 0
    links: List[str] = []
    while True:
        a = text.find("<link>", start)
        if a == -1:
            break
        b = text.find("</link>", a)
        if b == -1:
            break
        link = text[a + 6 : b].strip()
        links.append(link)
        start = b + 7

    for link in links:
        if "/status/" in link:
            return link
    return None


def normalize_to_xdotcom(link: str) -> str:
    # 앵커 제거 (#m 등)
    link = link.split("#")[0]

    # nitter/xcancel 등을 x.com으로 치환
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


def post_to_discord_thread(webhook_url: str, thread_id: str, content: str) -> None:
    url = f"{webhook_url}?thread_id={thread_id}"
    payload = {"content": content}
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()


def process_account(account: str, state: Dict[str, str]) -> None:
    # thread_id / webhook 확인
    thread_id = THREAD_IDS.get(account)
    webhook = WEBHOOKS.get(account)

    if not thread_id or "PUT_" in thread_id:
        print(f"[{account}] thread_id not set. Skipping.")
        return
    if not webhook:
        print(f"[{account}] webhook not set. Skipping.")
        return

    latest_link = None
    used_source = None

    # 여러 RSS 소스 중 되는 것 하나를 사용
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

    # 중복 방지 (계정별)
    if state.get(account) == latest_link:
        print(f"[{account}] No new tweet.")
        return

    msg = f"{account} 최신 트윗:\n{latest_link}"
    post_to_discord_thread(webhook, thread_id, msg)

    state[account] = latest_link
    print(f"[{account}] Posted: {latest_link}")
    print(f"[{account}] Source: {used_source}")


def main() -> None:
    state = load_state()

    # 계정 2개 처리
    for account in ["imassc_official", "kadokawa_sk"]:
        process_account(account, state)

    save_state(state)


if __name__ == "__main__":
    main()
