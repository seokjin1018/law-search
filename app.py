from flask import Flask, render_template, request, jsonify
import json, re

app = Flask(__name__)

with open("precedents_data_cleaned_clean.json", encoding="utf-8-sig") as f:
    data = json.load(f)

def clean_text(text):
    return re.sub(r"\s+", "", text)  # 모든 공백 제거

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

# 🔹 공백만 제거해서 비교
def matches_ignore_space(keyword, target):
    kw_norm = re.sub(r"\s+", "", keyword)
    target_norm = re.sub(r"\s+", "", target)
    return kw_norm in target_norm

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

            # 제외 키워드
            if exclude and any(matches_ignore_space(ex, s) for s in strings for ex in exclude):
                continue

            # 검색 모드별 처리
            if mode == "SINGLE":
                if keywords and any(matches_ignore_space(keywords[0], s) for s in strings):
                    results.append(case)
            elif mode == "OR":
                if any(any(matches_ignore_space(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND":
                if all(any(matches_ignore_space(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND_OR":
                if len(keywords) >= 2:
                    if any(matches_ignore_space(keywords[0], s) for s in strings) and \
                       any(matches_ignore_space(kw, s) for s in strings for kw in keywords[1:]):
                        results.append(case)

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)