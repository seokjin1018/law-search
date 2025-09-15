from flask import Flask, render_template, request, jsonify
import json, re, os, sys
from datetime import datetime

app = Flask(__name__)

STRICT_DATA_CHECK = os.environ.get("STRICT_DATA_CHECK", "False").lower() == "true"

# ===== 데이터 로드 =====
data = {}
json_path = os.path.join(os.path.dirname(__file__), "precedents_data_cleaned_clean.json")
try:
    with open(json_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    total_cases = sum(len(c) for c in data.values())
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

# ===== 유틸 함수 =====
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

# 공백 무시 매칭
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

# 판례 정보에서 선고일 추출
def extract_date_from_info(info):
    info = re.sub(r"[\u200B-\u200D\uFEFF]", "", info)
    m = re.search(r"(대법원|헌법재판소)\s+(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*선고", info)
    if not m:
        return datetime.min
    try:
        return datetime(int(m.group(2)), int(m.group(3)), int(m.group(4)))
    except ValueError:
        return datetime.min

# ===== 라우트 =====
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/laws", methods=["GET"])
def get_laws():
    return jsonify(list(data.keys()))

@app.route("/search", methods=["POST"])
def search():
    mode = request.json.get("mode")
    keywords = request.json.get("keywords", [])
    exclude = request.json.get("exclude", [])
    selected_laws = request.json.get("laws") or []
    page = int(request.json.get("page", 1))
    page_size = int(request.json.get("pageSize", 20))
    sort_by = request.json.get("sortBy", "default")  # default, latest, oldest

    results = []
    matched_keywords = set()

    for law, cases in data.items():
        if selected_laws and "전체" not in selected_laws and law not in selected_laws:
            continue
        for case in cases:
            strings = get_all_strings(case)
            strings.append(law)

            # 제외 키워드 필터
            if exclude and any(strict_match(ex, s) for s in strings for ex in exclude):
                continue

            # ✅ 키워드 없으면 전체 통과
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)