import os
import json
import requests
from typing import Optional

# ✅ 감지(가져오기)용 RSS 소스 후보들 (인스턴스마다 차단/상태가 달라 여러 개 둠)
SOURCES = [
    "https://nitter.net/imassc_official/rss",
    "https://xcancel.com/imassc_official/rss",
    "https://nitter.poast.org/imassc_official/rss",
]

# ✅ 네가 올리고 싶은 "포럼 포스트(=스레드)" ID
THREAD_ID = "1452221967544619101"

# ✅ 중복 업로드 방지용 상태 파일
STATE_FILE = "state.json"

# ✅ GitHub Secrets에 저장한 웹훅 URL
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]

# ✅ 봇으로 보이지 않게 하는 User-Agent
UA = "Mozilla/5.0 (compatible; imassc-forwarder/1.0; +https://github.com/)"

def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_link": None}
    except json.JSONDecodeError:
        # state.json이 깨졌을 때 안전하게 초기화
        return {"last_link": None}

def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)

def fetch_latest_link_from_rss(url: str) -> Optional[str]:
    """
    RSS(XML)에서 최신 트윗 status 링크를 1개 뽑아온다.
    외부 RSS 파서 없이 최소 파싱으로 동작하도록 작성.
    """
    r = requests.get(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        },
        timeout=20,
    )
    if r.status_code != 200:
        print(f"Fetch failed: {url} -> {r.status_code}")
        return None

    text = r.text

    # 단순 파싱: <link>...</link>들을 모두 모은 뒤 /status/ 포함 링크를 선택
    links = []
    start = 0
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
    """
    nitter/xcancel 등을 통해 얻은 링크를 최종적으로 x.com 링크로 변환.
    (#m 같은 앵커도 제거)
    """
    link = link.split("#")[0]  # 앵커 제거

    # 다양한 nitter 계열 도메인을 x.com으로 치환
    replacements = [
        ("https://nitter.net/", "https://x.com/"),
        ("https://xcancel.com/", "https://x.com/"),
        ("https://nitter.poast.org/", "https://x.com/"),
        ("http://nitter.net/", "https://x.com/"),
        ("http://xcancel.com/", "https://x.com/"),
        ("http://nitter.poast.org/", "https://x.com/"),
    ]
    for src, dst in replacements:
        if link.startswith(src):
            link = link.replace(src, dst, 1)
            break

    return link

def post_to_thread(content: str) -> None:
    """
    디스코드 웹훅으로 특정 스레드(포럼 포스트)에 메시지 전송.
    thread_id를 쿼리로 붙이면 해당 스레드에 들어간다.
    """
    url = f"{WEBHOOK}?thread_id={THREAD_ID}"
    payload = {"content": content}

    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()

def main() -> None:
    state = load_state()

    latest_link = None
    used_source = None

    # 여러 RSS 소스 중 되는 것에서 최신 링크를 가져옴
    for src in SOURCES:
        try:
            link = fetch_latest_link_from_rss(src)
            if link:
                latest_link = link
                used_source = src
                break
        except Exception as e:
            print(f"Error reading {src}: {e}")

    if not latest_link:
        print("Could not fetch latest tweet from any source.")
        return

    latest_link = normalize_to_xdotcom(latest_link)

    # 중복 방지
    if latest_link == state.get("last_link"):
        print("No new tweet.")
        return

    msg = f"테스트\n{latest_link}"
    post_to_thread(msg)

    state["last_link"] = latest_link
    save_state(state)

    print("Posted:", latest_link)
    print("Source:", used_source)

if __name__ == "__main__":
    main()
