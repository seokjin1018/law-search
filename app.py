from flask import Flask, render_template, request, jsonify
import json, re, os, sys

app = Flask(__name__)

# 운영 환경에서 데이터 없으면 서버 중단 여부 (True면 강제 종료)
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
            print(f"[DEBUG] keyword='{clean_keyword}', text='{clean_text}', pattern='{pattern}', match=True")
        return match_result
    else:
        match_result = clean_keyword in clean_text
        if match_result:
            print(f"[DEBUG] keyword='{clean_keyword}', text='{clean_text}', match=True")
        return match_result

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

    results = []
    for law, cases in data.items():
        if selected_laws and "전체" not in selected_laws and law not in selected_laws:
            continue
        for case in cases:
            strings = get_all_strings(case)
            strings.append(law)
            if exclude and any(strict_match(ex, s) for s in strings for ex in exclude):
                continue
            if mode == "SINGLE":
                if keywords and any(strict_match(keywords[0], s) for s in strings):
                    results.append(case)
            elif mode == "OR":
                if any(any(strict_match(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND":
                if all(any(strict_match(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND_OR":
                if len(keywords) >= 2:
                    if any(strict_match(keywords[0], s) for s in strings) and \
                       any(strict_match(kw, s) for s in strings for kw in keywords[1:]):
                        results.append(case)
    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render 환경 호환
    app.run(host="0.0.0.0", port=port, debug=False)