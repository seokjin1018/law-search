from flask import Flask, render_template, request, jsonify
import json, re
import os

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
        strings.append(clean_text(obj))
    return strings

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

    kw_clean = [clean_text(k) for k in keywords if k]
    ex_clean = [clean_text(k) for k in exclude if k]

    results = []
    for law, cases in data.items():
        if selected_laws and "전체" not in selected_laws and law not in selected_laws:
            continue
        law_clean = clean_text(law)
        for case in cases:
            strings = get_all_strings(case)
            strings.append(law_clean)
            if ex_clean and any(ex in s for s in strings for ex in ex_clean):
                continue
            if mode == "SINGLE":
                if kw_clean and any(kw_clean[0] in s for s in strings):
                    results.append(case)
            elif mode == "OR":
                if any(any(kw in s for s in strings) for kw in kw_clean):
                    results.append(case)
            elif mode == "AND":
                if all(any(kw in s for s in strings) for kw in kw_clean):
                    results.append(case)
            elif mode == "AND_OR":
                if len(kw_clean) >= 2:
                    if any(kw_clean[0] in s for s in strings) and \
                       any(kw in s for s in strings for kw in kw_clean[1:]):
                        results.append(case)
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)