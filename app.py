from flask import Flask, render_template, request, jsonify
import json, csv, re, os, sys
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# =========================
# 기존 판례검색기 데이터 로드 (JSON)
# =========================
STRICT_DATA_CHECK = os.environ.get("STRICT_DATA_CHECK", "False").lower() == "true"

data_json = {}
json_path = os.path.join(os.path.dirname(__file__), "precedents_data_cleaned_clean.json")
try:
    with open(json_path, encoding="utf-8-sig") as f:
        data_json = json.load(f)
    total_cases = sum(len(c) for c in data_json.values())
    print(f"[INFO] 로드된 판례 수: {total_cases}")
    if total_cases == 0 and STRICT_DATA_CHECK:
        print("[오류] 데이터가 비어 있습니다. 서버를 종료합니다.")
        sys.exit(1)
    elif total_cases == 0:
        print("[경고] 데이터가 비어 있습니다. 검색 결과가 항상 빈 값이 반환됩니다.")
except FileNotFoundError:
    print(f"[오류] 데이터 파일을 찾을 수 없습니다: {json_path}")
    if STRICT_DATA_CHECK:
        sys.exit(1)
except json.JSONDecodeError as e:
    print(f"[오류] JSON 파싱 오류: {e}")
    if STRICT_DATA_CHECK:
        sys.exit(1)

# ===== 기존 검색기 유틸 =====
def get_all_strings(obj):
    strings = []
    if isinstance(obj, dict):
        for v in obj.values():
            strings.extend(get_all_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(get_all_strings(item))
    elif isinstance(obj, str):
        strings.append(obj)
    else:
        strings.append(str(obj))
    return strings

# 공백/제로폭 문자 제거 후 포함 매칭
def strict_match(keyword, text):
    clean_text = re.sub(r"\s+", "", re.sub(r"[\u200B-\u200D\uFEFF]", "", text))
    clean_keyword = re.sub(r"\s+", "", re.sub(r"[\u200B-\u200D\uFEFF]", "", keyword))
    return clean_keyword in clean_text

# 키워드 하이라이트
def highlight_matches(text, keywords):
    if not isinstance(text, str):
        return text
    highlighted = text
    for kw in keywords:
        if len(kw) > 1:
            pattern = r"(" + r"\s*".join(map(re.escape, kw)) + r")"
        else:
            pattern = re.escape(kw)
        highlighted = re.sub(pattern, r"<mark>\1</mark>", highlighted, flags=re.IGNORECASE)
    return highlighted

# "판례 정보"에서 선고일 추출
def extract_date_from_info(info):
    info = re.sub(r"[\u200B-\u200D\uFEFF]", "", info)
    m = re.search(r"(대법원|헌법재판소)\s+(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*선고", info)
    if not m:
        return datetime.min
    try:
        return datetime(int(m.group(2)), int(m.group(3)), int(m.group(4)))
    except ValueError:
        return datetime.min

# =========================
# 형사 최신 판례 데이터 로드 (CSV)
# =========================
CSV_PATH = os.path.join(os.path.dirname(__file__), "정리본.csv")

criminal_rows = []
criminal_laws_dict = defaultdict(set)
criminal_all_laws = []
ARTICLE_RE = re.compile(r"^제\d+조(?:의\d+)?(?:-\d+)?$")

def is_article_token(tok: str) -> bool:
    return bool(ARTICLE_RE.match(tok))

def parse_refs_to_law_and_article(ref: str):
    # 쉼표/괄호 제거 후 토큰화 → 법령명 토큰/조문 토큰 분리
    ref = re.sub(r"[,\(\)]", " ", ref).strip()
    tokens = ref.split()
    law_tokens, article_tokens = [], []
    for tok in tokens:
        if is_article_token(tok):
            article_tokens.append(tok)
        elif not article_tokens:
            law_tokens.append(tok)
        else:
            article_tokens.append(tok)
    law = " ".join(law_tokens).strip()
    article = " ".join(article_tokens).strip()
    return law, article

def load_criminal_csv():
    global criminal_rows, criminal_laws_dict, criminal_all_laws
    criminal_rows = []
    criminal_laws_dict.clear()

    if not os.path.exists(CSV_PATH):
        print(f"[경고] 형사 최신 판례 CSV를 찾을 수 없습니다: {CSV_PATH}")
        criminal_all_laws = []
        return

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            for k in list(r.keys()):
                r[k] = (r[k] or "").strip()
            criminal_rows.append(r)

            # 참조조문에서 (법령, 조문) 추출
            refs = [p.strip() for p in (r.get("참조조문") or "").split(",") if p.strip()]
            last_law = None
            for ref in refs:
                law, article = parse_refs_to_law_and_article(ref)
                if law:
                    last_law = law
                elif last_law and article:
                    law = last_law
                if law and article:
                    criminal_laws_dict[law].add(article)

    # 조문 정렬 (숫자 우선)
    def sort_article_key(x: str):
        m = re.search(r"\d+", x)
        n = int(m.group()) if m else 0
        tail = x
        return (n, tail)

    for k in list(criminal_laws_dict.keys()):
        criminal_laws_dict[k] = sorted(criminal_laws_dict[k], key=sort_article_key)

    criminal_all_laws = sorted(criminal_laws_dict.keys())

def strip_zero_width_and_spaces(s: str) -> str:
    s = re.sub(r"[\u200B-\u200D\uFEFF]", "", s or "")
    return re.sub(r"\s+", "", s)

def criminal_strict_match(keyword: str, text: str) -> bool:
    if not keyword:
        return False
    return strip_zero_width_and_spaces(keyword) in strip_zero_width_and_spaces(text or "")

def criminal_highlight_matches(text, keywords):
    if not isinstance(text, str) or not keywords:
        return text
    highlighted = text
    for kw in keywords:
        if not kw:
            continue
        parts = list(map(re.escape, kw))
        pattern = r"(" + r"\s*".join(parts) + r")" if len(parts) > 1 else r"(" + re.escape(kw) + r")"
        try:
            highlighted = re.sub(pattern, r"<mark>\1</mark>", highlighted, flags=re.IGNORECASE)
        except re.error:
            pass
    return highlighted

def parse_korean_date(s: str) -> datetime:
    s = (s or "").strip()
    m = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", s)
    if not m:
        return datetime.min
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return datetime.min

# 검색 결과용 참조조문 그룹핑
def group_reference_articles(text: str) -> str:
    if not text:
        return ""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    grouped = {}
    for p in parts:
        m = re.match(r"^(.*?)\s*(제\d+조.*)$", p)
        if m:
            law, article = m.group(1).strip(), m.group(2).strip()
            grouped.setdefault(law, []).append(article)
        else:
            grouped.setdefault("", []).append(p)
    result = []
    for law, articles in grouped.items():
        if not law:
            result.extend(articles)
        else:
            first = f"{law} {articles[0]}"
            rest = articles[1:]
            result.append(", ".join([first] + rest))
    return ", ".join(result)

def criminal_row_strings(r: dict):
    return [
        r.get("제목", ""),
        r.get("사건번호", ""),
        r.get("선고일자", ""),
        r.get("참조조문", ""),
        r.get("판시사항", "")
    ]

# 초기 로드 (형사 최신 판례)
load_criminal_csv()

# =========================
# 라우트
# =========================
@app.route("/")
def index():
    # index.html에 두 검색기 UI를 동시에 배치해 사용 가능합니다.
    return render_template("index.html")

# --- 기존 검색기 API ---
@app.route("/laws", methods=["GET"])
def get_laws():
    return jsonify(list(data_json.keys()))

@app.route("/search", methods=["POST"])
def search():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode")
    keywords = body.get("keywords", [])
    exclude = body.get("exclude", [])
    selected_laws = body.get("laws") or []
    page = int(body.get("page", 1))
    page_size = int(body.get("pageSize", 20))
    sort_by = body.get("sortBy", "default")  # default, latest, oldest

    results = []
    matched_keywords = set()

    for law, cases in data_json.items():
        if selected_laws and "전체" not in selected_laws and law not in selected_laws:
            continue
        for case in cases:
            strings = get_all_strings(case)
            strings.append(law)

            # 제외 키워드 필터
            if exclude and any(strict_match(ex, s) for s in strings for ex in exclude):
                continue

            # 키워드 매칭
            if not keywords:
                matched = True
            else:
                matched = False
                if mode == "SINGLE":
                    matched = any(strict_match(keywords[0], s) for s in strings)
                    if matched:
                        matched_keywords.add(keywords[0])
                elif mode == "OR":
                    for kw in keywords:
                        if any(strict_match(kw, s) for s in strings):
                            matched = True
                            matched_keywords.add(kw)
                elif mode == "AND":
                    if all(any(strict_match(kw, s) for s in strings) for kw in keywords):
                        matched = True
                        matched_keywords.update(keywords)
                elif mode == "AND_OR":
                    if len(keywords) >= 2:
                        if any(strict_match(keywords[0], s) for s in strings) and \
                           any(strict_match(kw, s) for s in strings for kw in keywords[1:]):
                            matched = True
                            matched_keywords.update(keywords)

            if matched:
                raw_info = case.get("판례 정보", "")
                sort_date = extract_date_from_info(raw_info)

                highlighted_case = {
                    k: highlight_matches(v, keywords) if isinstance(v, str) else v
                    for k, v in case.items()
                }
                highlighted_case["_sort_date"] = sort_date
                results.append(highlighted_case)

    # 디버그 로그
    for kw in matched_keywords:
        print(f"[DEBUG] keyword='{kw}', match=True")

    # 정렬
    if sort_by == "latest":
        results.sort(key=lambda x: x.get("_sort_date", datetime.min), reverse=True)
    elif sort_by == "oldest":
        results.sort(key=lambda x: x.get("_sort_date", datetime.min))

    for r in results:
        r.pop("_sort_date", None)

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = results[start:end]

    return jsonify({
        "total": total,
        "page": page,
        "pageSize": page_size,
        "results": paginated
    })

# --- 형사 최신 판례 API (prefix: /criminal) ---
@app.route("/criminal/laws", methods=["GET"])
def criminal_laws():
    return jsonify(criminal_all_laws)

@app.route("/criminal/articles", methods=["GET"])
def criminal_articles():
    law = request.args.get("law", "", type=str).strip()
    if not law or law not in criminal_laws_dict:
        return jsonify([])
    return jsonify(list(criminal_laws_dict[law]))

@app.route("/criminal/search", methods=["POST"])
def criminal_search():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "SINGLE")
    keywords = body.get("keywords", []) or []
    exclude = body.get("exclude", []) or []
    selected_law = (body.get("selectedLaw") or "").strip()
    selected_article = (body.get("selectedArticle") or "").strip()
    page = int(body.get("page", 1))
    page_size = int(body.get("pageSize", 20))
    sort_by = body.get("sortBy", "default")

    results = []

    for r in criminal_rows:
        strings = criminal_row_strings(r)

        # 제외 키워드
        if exclude and any(criminal_strict_match(ex, s) for s in strings for ex in exclude):
            continue

        # 키워드 매칭
        matched = False
        if keywords:
            if mode == "SINGLE":
                matched = any(criminal_strict_match(keywords[0], s) for s in strings)
            elif mode == "OR":
                matched = any(any(criminal_strict_match(kw, s) for s in strings) for kw in keywords)
            elif mode == "AND":
                matched = all(any(criminal_strict_match(kw, s) for s in strings) for kw in keywords)
            elif mode == "AND_OR":
                if len(keywords) >= 2:
                    first_ok = any(criminal_strict_match(keywords[0], s) for s in strings)
                    rest_ok = any(any(criminal_strict_match(kw, s) for s in strings) for kw in keywords[1:])
                    matched = first_ok and rest_ok
        else:
            matched = True  # 키워드 없으면 법령/조문만으로 필터 가능

        if not matched:
            continue

        # 법령/조문 필터
        if selected_law:
            law_ok = selected_law in (r.get("참조조문") or "")
            if not law_ok:
                continue
            if selected_article:
                pair = f"{selected_law} {selected_article}"
                if pair not in (r.get("참조조문") or ""):
                    continue

        sort_date = parse_korean_date(r.get("선고일자", ""))

        highlighted = {}
        for k, v in r.items():
            val = v
            if k == "참조조문":
                val = group_reference_articles(v)  # 검색 결과에서만 변환
            highlighted[k] = criminal_highlight_matches(val, keywords) if isinstance(val, str) else val

        highlighted["_sort_date"] = sort_date
        results.append(highlighted)

    # 정렬
    if sort_by == "latest":
        results.sort(key=lambda x: x.get("_sort_date", datetime.min), reverse=True)
    elif sort_by == "oldest":
        results.sort(key=lambda x: x.get("_sort_date", datetime.min))

    for r in results:
        r.pop("_sort_date", None)

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = results[start:end]

    return jsonify({
        "total": total,
        "page": page,
        "pageSize": page_size,
        "results": paginated
    })

# =========================
# 메인 실행
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)