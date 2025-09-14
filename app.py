from flask import Flask, render_template, request, jsonify
import json, re, os

app = Flask(__name__)

# 데이터 로드
data = {}
json_path = os.path.join(os.path.dirname(__file__), "precedents_data_cleaned_clean.json")
try:
    with open(json_path, encoding="utf-8-sig") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"[경고] 데이터 파일을 찾을 수 없습니다: {json_path}")
except json.JSONDecodeError as e:
    print(f"[경고] JSON 파싱 오류: {e}")

# 모든 문자열 추출
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
    return strings

# 글자 단위 공백 허용, 다른 문자는 불허
def strict_match(keyword, text):
    if len(keyword) > 1:
        pattern = r"".join(re.escape(ch) + r"\s*" for ch in keyword[:-1]) + re.escape(keyword[-1])
        return re.search(pattern, text) is not None
    else:
        return keyword in text

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

            # 제외 키워드 검사
            if exclude and any(strict_match(ex, s) for s in strings for ex in exclude):
                continue

            # 포함 키워드 검사
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)