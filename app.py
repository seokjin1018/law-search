from flask import Flask, render_template, request, jsonify
import json, re, os

app = Flask(__name__)

with open("precedents_data_cleaned_clean.json", encoding="utf-8-sig") as f:
    data = json.load(f)

def clean_text(text):
    return re.sub(r"\s+", "", text)

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

def keyword_match(keyword, text):
    if len(keyword) >= 2:
        pattern = re.escape(keyword[0]) + r"\s*" + re.escape(keyword[1:])
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
            if exclude and any(keyword_match(ex, s) for s in strings for ex in exclude):
                continue
            if mode == "SINGLE":
                if keywords and any(keyword_match(keywords[0], s) for s in strings):
                    results.append(case)
            elif mode == "OR":
                if any(any(keyword_match(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND":
                if all(any(keyword_match(kw, s) for s in strings) for kw in keywords):
                    results.append(case)
            elif mode == "AND_OR":
                if len(keywords) >= 2:
                    if any(keyword_match(keywords[0], s) for s in strings) and \
                       any(keyword_match(kw, s) for s in strings for kw in keywords[1:]):
                        results.append(case)
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)