import os
import json
import requests

# 여러 소스 후보 중 "되는 것"을 쓰면 됨.
# (오라클 VM에서 막혔던 곳도, GitHub Actions에서는 되는 경우가 많음)
SOURCES = [
    # Nitter 계열은 인스턴스마다 차단/상태가 달라서 여러 개 후보를 둠
    "https://nitter.net/imassc_official/rss",
    "https://xcancel.com/imassc_official/rss",
    "https://nitter.poast.org/imassc_official/rss",
]

THREAD_ID = "1452221967544619101"  # 목표 포럼 포스트(스레드) ID
STATE_FILE = "state.json"

WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]

UA = "Mozilla/5.0 (compatible; imassc-forwarder/1.0; +https://github.com/)"

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_link": None}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)

def fetch_latest_link_from_rss(url: str) -> str | None:
    # RSS 파싱 라이브러리 없이도 최소 파싱으로 "첫 item의 link"를 잡는 버전
    # (RSS가 표준 XML이면 대부분 동작)
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"}, timeout=20)
    if r.status_code != 200:
        return None

    text = r.text
    # 아주 단순한 파싱: 첫 <link>...</link> 중 트윗 링크에 가까운 것을 잡기
    # RSS 형태가 다르면 여기만 바꿔주면 됨.
    links = []
    start = 0
    while True:
        a = text.find("<link>", start)
        if a == -1: break
        b = text.find("</link>", a)
        if b == -1: break
        link = text[a+6:b].strip()
        links.append(link)
        start = b + 7

    # 보통 첫 번째 link는 채널 링크(프로필)라서, 트윗 링크를 찾음
    for link in links:
        if "/status/" in link:
            return link
    return None

def post_to_thread(content: str):
    # Discord 공식 문서: thread_id를 쿼리로 붙이면 해당 스레드에 전송됨 :contentReference[oaicite:2]{index=2}
    url = f"{WEBHOOK}?thread_id={THREAD_ID}"
    payload = {"content": content}
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()

def main():
    state = load_state()

    latest_link = None
    used_source = None
    for src in SOURCES:
        try:
            link = fetch_latest_link_from_rss(src)
            if link:
                latest_link = link
                used_source = src
                break
        except Exception:
            pass

    if not latest_link:
        print("Could not fetch latest tweet from any source.")
        return

    if latest_link == state["last_link"]:
        print("No new tweet.")
        return

    msg = f"야\n{latest_link}"
    post_to_thread(msg)

    state["last_link"] = latest_link
    save_state(state)
    print("Posted:", latest_link)
    print("Source:", used_source)

if __name__ == "__main__":
    main()
