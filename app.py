from flask import Flask, render_template, request, jsonify
import json, re

app = Flask(__name__)

# 데이터 로드
with open("precedents_data_cleaned_clean.json", encoding="utf-8-sig") as f:
    data = json.load(f)

def get_all_strings(obj):
    """판례 데이터에서 모든 문자열 추출 (공백 유지)"""
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

# 🔹 공백 무시 + 정확 단어 매칭
def matches_ignore_space_exact(keyword, target):
    # 검색어와 대상에서 공백 제거
    kw_norm = re.sub(r"\s+", "", keyword)
    target_norm = re.sub(r"\s+", "", target)
    # 정확히 같은 단어일 때만 매칭
    return kw_norm == target_norm

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
            strings.append(law)  # 법령명도 검색 대상에 포함

            # 제외 키워드 처리
            if exclude and any(matches_ignore_space_exact(ex, s) for s in strings for ex in exclude):
                continue

            # 검색 모드별 처리
            if mode == "SINGLE":
                if keywords and any(matches_ignore_space_exact(keywords[0], s) for s in strings):
                    results.append(case)
            elif mode == "OR":
                if any(any(matches_ignore_space_exact(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND":
                if all(any(matches_ignore_space_exact(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND_OR":
                if len(keywords) >= 2:
                    if any(matches_ignore_space_exact(keywords[0], s) for s in strings) and \
                       any(matches_ignore_space_exact(kw, s) for s in strings for kw in keywords[1:]):
                        results.append(case)

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)