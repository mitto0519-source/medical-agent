"""KYRBS 원시자료 자동 다운로드 스크립트 (2005~2025, 전 차수).

사용법:
    python scripts/download_kyrbs.py             # 전체 다운로드
    python scripts/download_kyrbs.py --year 2024 # 특정 연도만
    python scripts/download_kyrbs.py --codebook  # 코드북만
    python scripts/download_kyrbs.py --no-extract # ZIP만, .sav 압축해제 생략

다운로드 위치: data/raw/kyrbs{year}.sav
코드북 위치:   data/raw/kyrbs_codebook_2005_2025.zip
"""
import argparse
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    print("requests 설치 필요: pip install requests")
    sys.exit(1)

RAW_DIR = Path("data/raw")

# (fileKey, fileId, filename)  — C024003 = SPSS 형식
FILES: dict[int, tuple[str, str, str]] = {
    2025: ("20251230165026610",  "202512301650266102151772",  "kyrbs2025_sav.zip"),
    2024: ("20241202083823822",  "202412020838238222138072",  "kyrbs2024_sav.zip"),
    2023: ("20240409140731649",  "202404091407316491396460",  "kyrbs2023.zip"),
    2022: ("20240411092324091",  "202404110923240911492809",  "kyrbs2022.zip"),
    2021: ("20240411092302236",  "202404110923022361396944",  "kyrbs2021_spss.zip"),
    2020: ("20240411092238465",  "202404110922384651397088",  "kyrbs2020_spss.zip"),
    2019: ("20240411092215065",  "202404110922150651396943",  "kyrbs2019_spss.zip"),
    2018: ("20240411092148761",  "202404110921487611397084",  "kyrbs2018_spss.zip"),
    2017: ("20240411092124129",  "202404110921241291397082",  "kyrbs2017_spss.zip"),
    2016: ("20240411092101009",  "202404110921010091397079",  "kyrbs2016_spss.zip"),
    2015: ("20240411092032305",  "202404110920323051397075",  "kyrbs2015_spss.zip"),
    2014: ("20240411092004201",  "202404110920042011397073",  "kyrbs2014_spss.zip"),
    2013: ("20240411091930561",  "202404110919305611396942",  "kyrbs2013_spss.zip"),
    2012: ("2017120508022012",   "2017120508022012434908",    "제8차(2012년) 청소년건강행태조사 DB_SPSS.zip"),
    2011: ("2017120508022011",   "2017120508022011434905",    "제7차(2011년) 청소년건강행태조사 DB_SPSS.zip"),
    2010: ("2017120508022010",   "2017120508022010434931",    "제6차(2010년) 청소년건강행태조사 DB_SPSS.zip"),
    2009: ("20171205080220091020810", "20171205080220091020810", "제5차(2009년) 청소년건강행태조사 DB_SPSS.zip"),
    2008: ("2017120508022008",   "2017120508022008434928",    "제4차(2008년) 청소년건강행태조사 DB_SPSS.zip"),
    2007: ("2017120508022007",   "2017120508022007434877",    "제3차(2007년) 청소년건강행태조사 DB_SPSS.zip"),
    2006: ("2017120508022006",   "2017120508022006709706",    "제2차(2006년) 청소년건강행태조사 DB_SPSS.zip"),
    2005: ("2017120508022005",   "2017120508022005434925",    "제1차(2005년) 청소년건강행태조사 DB_SPSS.zip"),
}

CODEBOOK = (
    "20260109094345322",
    "202601090943453222189624",
    "제1차(2005)_제21차(2025) 청소년건강행태조사 원시자료 이용지침서.zip",
)

POPUP_BASE = "https://www.kdca.go.kr/yhs/yhshmpg/result/yhsresult/rawDtaUseAgrePopup.do"
LIST_URL   = "https://www.kdca.go.kr/yhs/yhshmpg/result/yhsresult/rawDtaList.do"


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Referer": LIST_URL,
    })
    s.verify = False
    s.get(LIST_URL, timeout=20)  # establish session cookie
    return s


def get_download_url(s: requests.Session, file_key: str, file_id: str,
                     year: int | str, file_type: str, filename: str) -> str | None:
    from urllib.parse import quote
    params = (
        f"fileKey={file_key}&fileId={file_id}&dtaYear={year}"
        f"&fileTyCode={file_type}&fileNm={quote(filename)}"
    )
    r = s.get(f"{POPUP_BASE}?{params}", timeout=20)
    m = re.search(r"refile\.do\?[^'\"<>\s]+", r.text.replace("&amp;", "&"))
    if m:
        return "https://is.kdca.go.kr/uploadcomm/" + m.group(0)
    return None


def download_file(s: requests.Session, url: str, out_path: Path) -> int:
    r = s.get(url, timeout=180, stream=True)
    r.raise_for_status()
    total = 0
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)
            total += len(chunk)
    return total


def extract_sav(zip_path: Path, year: int) -> Path | None:
    with zipfile.ZipFile(zip_path) as z:
        sav_files = [n for n in z.namelist() if n.lower().endswith(".sav")]
        if not sav_files:
            return None
        target = RAW_DIR / f"kyrbs{year}.sav"
        with z.open(sav_files[0]) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return target


def main():
    parser = argparse.ArgumentParser(description="KYRBS 원시자료 다운로드")
    parser.add_argument("--year", type=int, help="특정 연도만 다운로드")
    parser.add_argument("--codebook", action="store_true", help="코드북만 다운로드")
    parser.add_argument("--no-extract", action="store_true", help="ZIP만 다운로드, .sav 압축해제 생략")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("세션 초기화 중...")
    s = make_session()

    years = [args.year] if args.year else sorted(FILES.keys(), reverse=True)

    if not args.codebook:
        for year in years:
            if year not in FILES:
                print(f"{year}: 지원하지 않는 연도 (2005~2025)")
                continue
            sav_path = RAW_DIR / f"kyrbs{year}.sav"
            if sav_path.exists():
                print(f"{year}: SKIP (kyrbs{year}.sav 이미 존재, {sav_path.stat().st_size//1024//1024}MB)")
                continue

            fk, fi, fn = FILES[year]
            zip_path = RAW_DIR / f"kyrbs{year}_spss.zip"

            if not zip_path.exists():
                try:
                    dl_url = get_download_url(s, fk, fi, year, "C024003", fn)
                    if not dl_url:
                        print(f"{year}: 다운로드 URL 획득 실패")
                        continue
                    print(f"{year}: 다운로드 중...", end=" ", flush=True)
                    size = download_file(s, dl_url, zip_path)
                    if size < 10000:
                        zip_path.unlink()
                        print(f"실패 (응답 {size}B)")
                        continue
                    print(f"{size//1024}KB OK")
                    time.sleep(1)
                except Exception as e:
                    print(f"\n{year}: ERROR {e}")
                    continue

            if not args.no_extract:
                try:
                    sav = extract_sav(zip_path, year)
                    if sav:
                        print(f"{year}: 압축 해제 → {sav.name} ({sav.stat().st_size//1024//1024}MB)")
                except Exception as e:
                    print(f"{year}: 압축 해제 실패 — {e}")

    # Codebook
    if args.codebook or not args.year:
        cb_path = RAW_DIR / "kyrbs_codebook_2005_2025.zip"
        if cb_path.exists():
            print(f"코드북: SKIP (이미 존재, {cb_path.stat().st_size//1024}KB)")
        else:
            fk, fi, fn = CODEBOOK
            try:
                dl_url = get_download_url(s, fk, fi, 2019, "C024004", fn)
                if dl_url:
                    print("코드북 다운로드 중...", end=" ", flush=True)
                    size = download_file(s, dl_url, cb_path)
                    print(f"{size//1024}KB OK")
            except Exception as e:
                print(f"코드북 ERROR {e}")

    print("\n완료.")


if __name__ == "__main__":
    main()
