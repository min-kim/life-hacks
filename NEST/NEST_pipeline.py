import json
import re
import sqlite3
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import quote

import pandas as pd
import PublicDataReader as pdr
import requests
import streamlit as st

# ==========================================
# 1. [사용자 설정] API 키 및 타겟 지역 설정 (서울 25개 자치구 전체)
# ==========================================

# 수정: secrets.toml 파일의 [AUCTION_API_KEY] 키 값을 읽어옴
KAKAO_API_KEY = st.secrets["KAKAO_API_KEY"]
PUBLIC_DATA_SERVICE_KEY = st.secrets["PUBLIC_DATA_SERVICE_KEY"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

TARGET_REGIONS = [
    {
        "city": ["서울", "서울특별시", "서울시"],
        "district": [
            "강서구",
            "강서",
            "양천구",
            "양천",
            "구로구",
            "구로",
            "금천구",
            "금천",
            "영등포구",
            "영등포",
            "동작구",
            "동작",
            "관악구",
            "관악",
            "마포구",
            "마포",
            "서대문구",
            "서대문",
            "은평구",
            "은평",
            "종로구",
            "종로",
            "중구",
            "용산구",
            "용산",
            "성동구",
            "성동",
            "광진구",
            "광진",
            "동대문구",
            "동대문",
            "중랑구",
            "중랑",
            "성북구",
            "성북",
            "강북구",
            "강북",
            "도봉구",
            "도봉",
            "노원구",
            "노원",
            "강남구",
            "강남",
            "서초구",
            "서초",
            "송파구",
            "송파",
            "강동구",
            "강동",
        ],
    }
]


def is_target_region(address: str, target_regions: list) -> bool:
    if not address:
        return False

    for region in target_regions:
        city_match = any(city in address for city in region["city"])
        district_match = any(dist in address for dist in region["district"])

        if city_match and district_match:
            return True

    return False


DB_FILE = "nest_auction_vault.db"
building_api = pdr.BuildingLedger(PUBLIC_DATA_SERVICE_KEY)

# ==========================================
# 2. 서울 전역 법원 딕셔너리 및 세션 동기화 크롤러
# ==========================================
SEOUL_COURTS = {
    "서울중앙지방법원": "B000210",
    "서울동부지방법원": "B000211",
    "서울서부지방법원": "B000215",
    "서울남부지방법원": "B000212",
    "서울북부지방법원": "B000213",
}


def sync_court_session(session, court_code):
    """대법원 서버에 해당 법원을 먼저 선택했다고 알려주는 세션 동기화 함수"""
    sync_url = "https://www.courtauction.go.kr/pgj/pgjsearch/selectCortOfcDeptLst.on"
    payload = {"dma_srchGdsDtlSrchInfo": {"cortOfcCd": court_code}}
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": (
            "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
        ),
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"
        ),
        "submissionid": "mf_wfm_mainFrame_sbm_selectCortOfcDeptLst",
    }
    try:
        session.post(sync_url, json=payload, headers=headers, timeout=5)
    except Exception:
        pass


def fetch_filtered_auction_properties(
    court_name="서울남부지방법원",
    court_code="B000212",
    building_type="빌라",
    max_items=None,  # None 설정 시 전수 수집
) -> list:
    print(f"🌐 [API 연동] {court_name} 직접 요청 시작 | 매물유형: {building_type}")
    raw_properties = []

    session = requests.Session()
    sync_court_session(session, court_code)

    today = datetime.now()
    future_date = today + timedelta(days=14)
    start_ymd = today.strftime("%Y%m%d")
    end_ymd = future_date.strftime("%Y%m%d")

    api_url = "https://www.courtauction.go.kr/pgj/pgjsearch/searchControllerMain.on"

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Content-Type": "application/json;charset=UTF-8",
        "Host": "www.courtauction.go.kr",
        "Origin": "https://www.courtauction.go.kr",
        "Referer": (
            "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
        ),
        "SC-Userid": "SYSTEM",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"
        ),
        "submissionid": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch",
    }

    page_no = 1

    while True:
        payload_data = {
            "dma_pageInfo": {
                "pageNo": page_no,
                "pageSize": 50,
                "bfPageNo": "",
                "startRowNo": "",
                "totalCnt": "",
                "totalYn": "Y",
                "groupTotalCount": "",
            },
            "dma_srchGdsDtlSrchInfo": {
                "rletDspslSpcCondCd": "",
                "bidDvsCd": "",
                "mvprpRletDvsCd": "00031R",
                "cortAuctnSrchCondCd": "0004601",
                "rprsAdongSdCd": "",
                "rprsAdongSggCd": "",
                "rprsAdongEmdCd": "",
                "rdnmSdCd": "",
                "rdnmSggCd": "",
                "rdnmNo": "",
                "mvprpDspslPlcAdongSdCd": "",
                "mvprpDspslPlcAdongSggCd": "",
                "mvprpDspslPlcAdongEmdCd": "",
                "rdDspslPlcAdongSdCd": "",
                "rdDspslPlcAdongSggCd": "",
                "rdDspslPlcAdongEmdCd": "",
                "cortOfcCd": court_code,
                "jdbnCd": "",
                "execrOfcDvsCd": "",
                "lclDspslGdsLstUsgCd": "20000",
                "mclDspslGdsLstUsgCd": "20100",
                "sclDspslGdsLstUsgCd": "",
                "cortAuctnMbrsId": "",
                "aeeEvlAmtMin": "",
                "aeeEvlAmtMax": "300000000",
                "lwsDspslPrcRateMin": "",
                "lwsDspslPrcRateMax": "",
                "flbdNcntMin": "",
                "flbdNcntMax": "",
                "objctArDtsMin": "",
                "objctArDtsMax": "",
                "mvprpArtclKndCd": "",
                "mvprpArtclNm": "",
                "mvprpAtchmPlcTypCd": "",
                "notifyLoc": "off",
                "lafjOrderBy": "",
                "pgmId": "PGJ151F01",
                "csNo": "",
                "cortStDvs": "1",
                "statNum": 1,
                "bidBgngYmd": start_ymd,
                "bidEndYmd": end_ymd,
                "dspslDxdyYmd": "",
                "fstDspslHm": "",
                "scndDspslHm": "",
                "thrdDspslHm": "",
                "fothDspslHm": "",
                "dspslPlcNm": "",
                "lwsDspslPrcMin": "",
                "lwsDspslPrcMax": "",
                "grbxTypCd": "",
                "gdsVendNm": "",
                "fuelKndCd": "",
                "carMdyrMax": "",
                "carMdyrMin": "",
                "carMdlNm": "",
                "sideDvsCd": "",
            },
        }

        try:
            response = session.post(api_url, json=payload_data, headers=headers)
            if response.status_code != 200:
                break

            res_json = response.json()
            items = []
            for key, val in res_json.items():
                if isinstance(val, list) and len(val) > 0:
                    items = val
                    break
                elif isinstance(val, dict):
                    for sub_k, sub_v in val.items():
                        if isinstance(sub_v, list) and len(sub_v) > 0:
                            items = sub_v
                            break

            if not items:
                break

            print(f"   [+] {page_no}페이지 수신 완료 (항목 수: {len(items)}개)")

            for item in items:
                case_no = item.get("srnSaNo") or item.get("csNo") or ""
                address_raw = item.get("printSt") or item.get("rdAddrSub") or ""
                buld_list = item.get("buldList", "")
                usg_nm = item.get("dspslUsgNm", "")

                if not case_no or not address_raw:
                    continue

                if (
                    "오피스텔" in usg_nm
                    or "오피스텔" in address_raw
                    or "오피스텔" in buld_list
                ):
                    continue

                year_match = re.search(r"(20\d{2})", case_no)
                if year_match and int(year_match.group(1)) <= 2023:
                    continue

                try:
                    yuchal_cnt = int(item.get("yuchalCnt", 0))
                    gameval_amt = float(item.get("gamevalAmt", 0))
                    minmae_price = float(item.get("minmaePrice", 0))
                except ValueError:
                    yuchal_cnt, gameval_amt, minmae_price = 0, 0, 0

                if yuchal_cnt > 10:
                    continue
                if gameval_amt > 0 and (minmae_price / gameval_amt) < 0.4:
                    continue

                floor_match = re.search(
                    r"(?:제)?(\d+)층", buld_list + " " + address_raw
                )
                floor = int(floor_match.group(1)) if floor_match else 1

                if not any(p["id"] == case_no for p in raw_properties):
                    raw_properties.append(
                        {
                            "id": case_no,
                            "court_name": court_name,
                            "address": address_raw,
                            "building_type": building_type,
                            "floor": floor,
                            "direction": "남향",
                        }
                    )

                if max_items and len(raw_properties) >= max_items:
                    break

            if len(items) < 50:  # 마지막 페이지 달성 시 루프 종료
                break

            if max_items and len(raw_properties) >= max_items:
                break

            page_no += 1

        except Exception as e:
            print(f"   [!] API 통신 중 예외 발생: {e}")
            break

    print(f"   [+] 최종 유효 매물 추출 완료: 총 {len(raw_properties)}개")
    return raw_properties


def fetch_all_seoul_auctions(building_type="빌라", max_items_per_court=None):
    total_properties = []
    print("🚀 [전체 시작] 서울 전역 주요 법원 경매 매물 수집을 시작합니다...")

    for court_name, court_code in SEOUL_COURTS.items():
        print(f"\n🔍 [{court_name}] 매물 검색 시작...")
        props = fetch_filtered_auction_properties(
            court_name=court_name,
            court_code=court_code,
            building_type=building_type,
            max_items=max_items_per_court,
        )
        total_properties.extend(props)

    print(
        f"\n✨ [수집 완료] 서울 전역 총 {len(total_properties)}개의 유효 매물이"
        " 확보되었습니다."
    )
    return total_properties


# ==========================================
# 3. SQLite DB 관리 모듈
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_auctions (
            id TEXT PRIMARY KEY,
            court_name TEXT,
            address TEXT,
            score REAL,
            min_park_dist REAL,
            study_infra_count INTEGER,
            has_elevator INTEGER,
            is_top_floor INTEGER,
            naver_link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def is_already_processed(auction_id):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM processed_auctions WHERE id = ?", (auction_id,))
        result = cursor.fetchone()
    except sqlite3.OperationalError:
        init_db()
        cursor.execute("SELECT 1 FROM processed_auctions WHERE id = ?", (auction_id,))
        result = cursor.fetchone()
    finally:
        conn.close()
    return result is not None


def save_auction_property(item):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO processed_auctions
        (id, court_name, address, score, min_park_dist, study_infra_count, has_elevator, is_top_floor, naver_link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            item["사건번호"],
            item["법원명"],
            item["주소"],
            item["최종점수"],
            item["공원과의거리(m)"],
            item["주변스카/도서관개수"],
            1 if item["엘리베이터설치"] else 0,
            1 if item["탑층여부"] else 0,
            item["네이버부동산_링크"],
        ),
    )
    conn.commit()
    conn.close()


# ==========================================
# 4. 텔레그램 연동 및 리포트 모듈
# ==========================================
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    headers = {"Content-Type": "application/json"}
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("   [+] 텔레그램 주간 요약 리포트 전송 완료!")
    except Exception as e:
        print(f"   [!] 텔레그램 전송 실패: {e}")


def format_weekly_report_msg(top_df: pd.DataFrame) -> str:
    if top_df.empty:
        return (
            "<b>📢 [주간 경매 리포트]</b>\n\n이번 주 검증을 통과한 추천"
            " 매물이 없습니다."
        )

    report_lines = [
        f"<b>📋 [주간 우수 경매 매물 TOP {len(top_df)} 리포트]</b>",
        "───────────────────",
    ]
    for idx, item in top_df.iterrows():
        rank = idx + 1
        court_info = f"[{item['법원명']}] " if item.get("법원명") else ""
        top_floor_str = "탑층" if item["탑층여부"] else "일반층"
        elvt_str = (
            f"승용 {item['엘리베이터대수']}대" if item["엘리베이터설치"] else "없음"
        )

        item_block = (
            f"<b>{rank}. {court_info}{item['사건번호']} (★"
            f" {item['최종점수']}점)</b>\n"
            f"• <b>주소:</b> {item['주소']}\n"
            f"• <b>층수/승강기:</b> {item['해당층']}층/{item['총층수']}층"
            f" ({top_floor_str}) | {elvt_str}\n"
            f"• <b>입지분석:</b> 공원 {item['공원과의거리(m)']}m | 스카/도서관"
            f" {item['주변스카/도서관개수']}개\n"
            f"• <b>바로가기:</b> <a"
            f" href='{item['네이버부동산_링크']}'>네이버시세</a> | <a"
            f" href='{item['법원경매_링크']}'>법원경매</a>"
        )
        report_lines.append(item_block)
        report_lines.append("───────────────────")

    report_lines.append("<i>※ 본 리포트는 자동 검증 필터를 통과한 매물입니다.</i>")
    return "\n".join(report_lines)


def generate_naver_land_url(address, dong_name="", building_type=None):
    parts = address.split()
    city = parts[0] if len(parts) > 0 else "서울"
    gu = parts[1] if len(parts) > 1 else "강서구"
    target_type = building_type if building_type else "아파트"
    if dong_name:
        region_keyword = f"{city} {gu} {dong_name}"
    elif len(parts) >= 3:
        region_keyword = f"{parts[0]} {parts[1]} {parts[2]}"
    else:
        region_keyword = address
    search_query = f"{region_keyword} {target_type}"
    return f"https://land.naver.com/search/search.naver?query={quote(search_query)}"


# ==========================================
# 5. 주소 분석 및 건축물대장 검증 모듈
# ==========================================
def extract_clean_road_address(address_str: str) -> str:
    if not address_str:
        return ""
    cleaned = address_str.strip()
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"해당층\s*:\s*\d+층?", "", cleaned)
    cleaned = re.sub(r"\b\d+동\b|\b\d+호\b|\b\d+층\b", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def get_coordinate_and_infra(address):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    clean_address = extract_clean_road_address(address)
    search_candidates = [
        ("address", address.strip()),
        ("address", clean_address),
        ("keyword", address.strip()),
        ("keyword", clean_address),
    ]
    match = re.search(r"([가-힣0-9]+(?:대로|로|길)\s+\d+(?:-\d+)?)", clean_address)
    if match:
        search_candidates.append(("address", match.group(1)))
        search_candidates.append(("keyword", match.group(1)))

    res_doc = None
    for api_type, query_str in search_candidates:
        if not query_str:
            continue
        url = f"https://dapi.kakao.com/v2/local/search/{api_type}.json"
        try:
            res = requests.get(
                url, headers=headers, params={"query": query_str}, timeout=5
            ).json()
            if res.get("documents"):
                res_doc = res["documents"][0]
                break
        except Exception:
            continue

    if not res_doc:
        return None

    lon = float(res_doc["x"])
    lat = float(res_doc["y"])
    sigungu_code = ""
    bdong_code = ""
    dong_name = ""
    main_no = "0"
    sub_no = "0"

    addr_obj = res_doc.get("address") or res_doc.get("road_address")
    if addr_obj:
        b_code = addr_obj.get("b_code", "")
        if b_code:
            sigungu_code = b_code[:5]
            bdong_code = b_code[5:10]
        main_no = addr_obj.get("main_address_no", "0")
        sub_no = addr_obj.get("sub_address_no", "0")
        dong_name = addr_obj.get("region_3depth_name", "")

    if not sigungu_code:
        try:
            coord_url = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
            coord_res = requests.get(
                coord_url, headers=headers, params={"x": lon, "y": lat}, timeout=3
            ).json()
            if coord_res.get("documents"):
                for reg in coord_res["documents"]:
                    if reg.get("region_type") == "B":
                        b_code = reg.get("code", "")
                        sigungu_code = b_code[:5]
                        bdong_code = b_code[5:10]
                        dong_name = reg.get("region_3depth_name", "")
                        break
        except Exception:
            pass

    def search_keyword(keyword, radius=500):
        kw_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        try:
            docs = (
                requests.get(
                    kw_url,
                    headers=headers,
                    params={
                        "query": keyword,
                        "x": lon,
                        "y": lat,
                        "radius": radius,
                        "sort": "distance",
                    },
                    timeout=3,
                )
                .json()
                .get("documents", [])
            )
            min_dist = min([float(d["distance"]) for d in docs]) if docs else 99999
            return len(docs), min_dist
        except Exception:
            return 0, 99999

    def search_category(category_code, radius=200):
        cat_url = "https://dapi.kakao.com/v2/local/search/category.json"
        try:
            return len(
                requests.get(
                    cat_url,
                    headers=headers,
                    params={
                        "category_group_code": category_code,
                        "x": lon,
                        "y": lat,
                        "radius": radius,
                    },
                    timeout=3,
                )
                .json()
                .get("documents", [])
            )
        except Exception:
            return 0

    park_count, min_park_dist = search_keyword("공원", radius=500)
    study_count, _ = search_keyword("스터디카페", radius=1000)
    office_count, _ = search_keyword("공유오피스", radius=1000)
    night_noise_count = search_category("DL6", radius=200)

    return {
        "lon": lon,
        "lat": lat,
        "dong_name": dong_name,
        "sigungu_code": sigungu_code,
        "bdong_code": bdong_code,
        "bun": str(main_no).zfill(4),
        "ji": str(sub_no).zfill(4),
        "min_park_dist": min_park_dist,
        "study_infra_count": study_count + office_count,
        "noise_score": night_noise_count,
    }


def verify_building_spec_real(infra_data, target_floor):
    if not infra_data or not infra_data.get("sigungu_code"):
        return {
            "status": "FAIL",
            "is_top_floor": False,
            "has_elevator": False,
            "is_violation": False,
            "total_floors": 0,
            "elevator_cnt": 0,
        }

    url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
    params = {
        "serviceKey": PUBLIC_DATA_SERVICE_KEY,
        "sigunguCd": infra_data["sigungu_code"],
        "bjdongCd": infra_data["bdong_code"],
        "platGbCd": "0",
        "bun": infra_data["bun"],
        "ji": infra_data["ji"],
        "_type": "json",
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            return {"status": "FAIL"}

        items = (
            res.json()
            .get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", {})
        )
        if not items:
            return {"status": "FAIL"}

        if isinstance(items, dict):
            items = [items]

        max_floors = 0
        total_elevators = 0
        is_violation = False

        for item in items:
            flr = int(item.get("grndFlrCnt") or 0)
            elvt = int(item.get("rideUseElvtCnt") or 0)
            viol = str(item.get("violBldOcrrYn") or "0")
            if flr > max_floors:
                max_floors = flr
            if elvt > total_elevators:
                total_elevators = elvt
            if viol == "1":
                is_violation = True

        has_elevator = total_elevators > 0
        try:
            target_flr_int = int(str(target_floor).replace("층", "").strip())
            is_top_floor = (target_flr_int == max_floors) if max_floors > 0 else False
        except Exception:
            is_top_floor = False

        return {
            "status": "SUCCESS",
            "is_top_floor": is_top_floor,
            "has_elevator": has_elevator,
            "is_violation": is_violation,
            "total_floors": max_floors,
            "elevator_cnt": total_elevators,
        }
    except Exception:
        return {"status": "FAIL"}


# ==========================================
# 6. 스코어링 및 메인 실행 파이프라인
# ==========================================
def calculate_property_score(prop, infra_data, spec_data):
    score = 50.0
    min_park_dist = infra_data["min_park_dist"]
    if min_park_dist <= 500:
        score += (500 - min_park_dist) / 25.0
    score += min(15, infra_data["study_infra_count"] * 2)
    if spec_data.get("has_elevator"):
        score += 5
    if spec_data.get("is_top_floor"):
        score += 5
    return round(score, 2)


def select_top_properties_df(perfect_list: list, top_n: int = 3) -> pd.DataFrame:
    if not perfect_list:
        return pd.DataFrame()
    df = pd.DataFrame(perfect_list)
    return (
        df.sort_values(by=["최종점수", "사건번호"], ascending=[False, False])
        .head(top_n)
        .reset_index(drop=True)
    )


def process_single_auction(prop):
    """단일 매물 1건에 대해 정밀 검증 수행 (멀티스레드 워커가 실행)"""
    auction_id = prop["id"]
    court_name = prop.get("court_name", "")
    address = prop["address"]
    target_floor = prop.get("floor", 0)

    if is_already_processed(auction_id):
        return None
    if not is_target_region(address, TARGET_REGIONS):
        return None

    infra_data = get_coordinate_and_infra(address)
    if not infra_data or infra_data["noise_score"] > 0:
        return None

    spec_data = verify_building_spec_real(infra_data, target_floor)
    if (
        spec_data.get("status") == "FAIL"
        or spec_data.get("is_violation")
        or not spec_data.get("has_elevator")
    ):
        return None

    final_score = calculate_property_score(prop, infra_data, spec_data)
    naver_land_url = generate_naver_land_url(
        address, infra_data.get("dong_name", ""), prop.get("building_type", "빌라")
    )

    prop_summary = {
        "사건번호": auction_id,
        "법원명": court_name,
        "주소": address,
        "해당층": target_floor,
        "총층수": spec_data["total_floors"],
        "최종점수": final_score,
        "공원과의거리(m)": round(infra_data["min_park_dist"], 1),
        "주변스카/도서관개수": infra_data["study_infra_count"],
        "엘리베이터설치": spec_data["has_elevator"],
        "엘리베이터대수": spec_data["elevator_cnt"],
        "탑층여부": spec_data["is_top_floor"],
        "네이버부동산_링크": naver_land_url,
        "네이버경매_링크": "https://land.naver.com/auction/",
        "법원경매_링크": "https://www.courtauction.go.kr/",
    }

    save_auction_property(prop_summary)
    return prop_summary


def evaluate_auction_properties_fast(
    raw_properties, top_n: int = 3, max_workers: int = 10
):
    """ThreadPoolExecutor를 통한 멀티스레딩 고속 검증"""
    init_db()

    print(
        f"\n⚡ [멀티스레딩 적용] 동시 작업 수: {max_workers}개로 검증을 시작합니다..."
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_auction, raw_properties))

    perfect_list = [res for res in results if res is not None]

    print(
        f"\n✨ [2단계 검증 완료] 총 {len(raw_properties)}개 중 {len(perfect_list)}개 매물이"
        " 정밀 검증 조건을 통과했습니다."
    )

    top_df = select_top_properties_df(perfect_list, top_n=top_n)
    if not top_df.empty:
        report_msg = format_weekly_report_msg(top_df)
        send_telegram_message(report_msg)

    return top_df


if __name__ == "__main__":
    # DB 및 테이블 초기화를 최우선으로 실행
    init_db()

    print("🚀 [1단계] 서울 전역 법원 실시간 경매 매물 수집 시작...")
    real_auction_data = fetch_all_seoul_auctions(building_type="빌라")

    if real_auction_data:
        print(
            f"\n🚀 [2단계] 수집된 총 {len(real_auction_data)}개 매물에 대한 정밀 검증"
            " 시작..."
        )
        # 멀티스레드 적용 함수로 실행 (기본동시성: 10개)
        top_recommendations = evaluate_auction_properties_fast(
            real_auction_data, top_n=3, max_workers=10
        )
    else:
        print("\n[!] 수집된 실시간 경매 매물이 없습니다.")
