from flask import Flask, render_template, request, jsonify
import json, re, os, sys

app = Flask(__name__)

STRICT_DATA_CHECK = os.environ.get("STRICT_DATA_CHECK", "False").lower() == "true"

# 데이터 로드
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

def strict_match(keyword, text):
    clean_text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    clean_keyword = re.sub(r"[\u200B-\u200D\uFEFF]", "", keyword)
    if len(clean_keyword) > 1:
        pattern = r"".join(re.escape(ch) + r"\s*" for ch in clean_keyword[:-1]) + re.escape(clean_keyword[-1])
        match_result = re.search(pattern, clean_text) is not None
        if match_result:
            print(f"[DEBUG] keyword='{clean_keyword}', match=True")
        return match_result
    else:
        match_result = clean_keyword in clean_text
        if match_result:
            print(f"[DEBUG] keyword='{clean_keyword}', match=True")
        return match_result

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

    results = []
    for law, cases in data.items():
        if selected_laws and "전체" not in selected_laws and law not in selected_laws:
            continue
        for case in cases:
            strings = get_all_strings(case)
            strings.append(law)
            if exclude and any(strict_match(ex, s) for s in strings for ex in exclude):
                continue
            matched = False
            if mode == "SINGLE":
                matched = keywords and any(strict_match(keywords[0], s) for s in strings)
            elif mode == "OR":
                matched = any(any(strict_match(kw, s) for s in strings) for kw in keywords)
            elif mode == "AND":
                matched = all(any(strict_match(kw, s) for s in strings) for kw in keywords)
            elif mode == "AND_OR":
                if len(keywords) >= 2:
                    matched = any(strict_match(keywords[0], s) for s in strings) and \
                              any(strict_match(kw, s) for s in strings for kw in keywords[1:])
            if matched:
                highlighted_case = {
                    k: highlight_matches(v, keywords) if isinstance(v, str) else v
                    for k, v in case.items()
                }
                results.append(highlighted_case)

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