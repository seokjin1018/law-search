from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import os
import json
import csv
import re
from datetime import datetime # <<<<<<<<<<< [추가] 날짜 정렬 기능을 위해 import
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3 # <<<<<<<<<<< [추가]

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = "your_secret_key"
CORS(app)

# ===== [추가] 데이터베이스 초기화 =====
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # users 테이블 생성: nickname, password, bookmarks(JSON 텍스트)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        bookmarks TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

# ===== 데이터 로드 =====
with open("precedents_data_cleaned_clean.json", "r", encoding="utf-8-sig") as f:
    law_dict = json.load(f)

LAWS = list(law_dict.keys())

CASES = []
for law_name, case_list in law_dict.items():
    for case in case_list:
        case["법령명"] = law_name
        CASES.append(case)

# ===== 형사 최신 판례 CSV 로드 =====
criminal_rows = []
criminal_all_laws = []
criminal_laws_dict = {}

def load_criminal_csv(path="정리본.csv"):
    global criminal_rows, criminal_all_laws, criminal_laws_dict
    criminal_rows = []
    law_set = set()
    mapping = {}

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            criminal_rows.append(row)
            ref = (row.get("참조조문") or "").strip()
            if not ref:
                continue
            parts = re.split(r"[,\n]", ref)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # 수정된 정규식: 법령 이름이 여러 단어인 경우를 올바르게 처리
                m = re.match(r"(.*?)\s*(제?\d+조.*)", part)
                if m:
                    law_name = m.group(1).strip()
                    article = m.group(2).strip()
                else:
                    law_name = part
                    article = ""
                if law_name:
                    law_set.add(law_name)
                    if law_name not in mapping:
                        mapping[law_name] = set()
                    if article:
                        mapping[law_name].add(article)

    criminal_all_laws = sorted(list(law_set))
    criminal_laws_dict = {k: sorted(list(v)) for k, v in mapping.items()}

load_criminal_csv()

# ===== 유틸리티 함수 =====
# <<<<<<<<<<< [추가] 정확한 날짜 정렬을 위한 헬퍼 함수
def normalize_date_for_sort(date_str):
    """정렬을 위해 다양한 날짜 형식을 'YYYYMMDD'로 변환합니다."""
    if not date_str:
        return "00000000"
    
    date_parts = re.findall(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', date_str)
    if date_parts:
        y, m, d = date_parts[0]
        return f"{y}{m.zfill(2)}{d.zfill(2)}"
    
    try:
        cleaned_str = re.sub(r'[^0-9]', '', date_str.split(',')[0])
        dt = datetime.strptime(cleaned_str, '%Y%m%d')
        return dt.strftime('%Y%m%d')
    except (ValueError, IndexError):
        return "00000000"

# <<<<<<<<<<< [수정] 띄어쓰기 무시 기능을 추가
def match_keywords(text, keywords, mode):
    if not keywords:
        return True
    
    text_no_space = text.lower().replace(" ", "")
    
    processed_keywords = [k.lower().replace(" ", "") for k in keywords if k.strip()]
    if not processed_keywords:
        return True

    if mode == "SINGLE":
        return processed_keywords[0] in text_no_space
    elif mode == "AND":
        return all(k in text_no_space for k in processed_keywords)
    elif mode == "OR":
        return any(k in text_no_space for k in processed_keywords)
    elif mode == "AND_OR":
        if len(processed_keywords) < 2:
            return processed_keywords[0] in text_no_space
        first, rest = processed_keywords[0], processed_keywords[1:]
        return first in text_no_space and any(k in text_no_space for k in rest)
    return True

# <<<<<<<<<<< [수정] 띄어쓰기 무시 기능을 추가
def exclude_keywords(text, exclude_list):
    if not exclude_list:
        return False
    
    text_no_space = text.lower().replace(" ", "")
    processed_exclude = [e.lower().replace(" ", "") for e in exclude_list if e.strip()]
    if not processed_exclude:
        return False
    
    return any(e in text_no_space for e in processed_exclude)

# ===== 라우트(API) =====
def process_search(items, data, date_key):
    """
    검색, 필터링, 정렬, 페이지네이션을 처리하는 공통 함수
    - items: 검색 대상 데이터 리스트 (CASES 또는 criminal_rows)
    - data: request.json()으로 받은 데이터
    - date_key: 날짜 정렬에 사용할 딕셔너리 키 ("판례 정보" 또는 "선고일자")
    """
    keywords = data.get("keywords", [])
    exclude = data.get("exclude", [])
    mode = data.get("mode", "SINGLE")
    sort_by = data.get("sortBy", "default")
    page = data.get("page", 1)
    page_size = data.get("pageSize", 20)

    # 키워드 및 제외어 필터링
    results = []
    for item in items:
        text_blob = " ".join(str(v) for v in item.values())
        if not match_keywords(text_blob, keywords, mode):
            continue
        if exclude_keywords(text_blob, exclude):
            continue
        results.append(item)

    # 날짜 기준 정렬
    if sort_by == "latest":
        results.sort(key=lambda x: normalize_date_for_sort(x.get(date_key, "")), reverse=True)
    elif sort_by == "oldest":
        results.sort(key=lambda x: normalize_date_for_sort(x.get(date_key, "")))
    
    # 페이지네이션
    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    return {"total": total, "results": results[start:end]}


@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/laws")
def get_laws():
    return jsonify(LAWS)

@app.route("/search", methods=["POST"])
def search_cases():
    """일반 판례 검색 API"""
    data = request.json
    laws = data.get("laws", [])
    
    # 일반 판례에만 해당하는 '법령명' 필터링 로직
    filtered_cases = CASES
    if laws and "전체" not in laws:
        filtered_cases = [case for case in CASES if case.get("법령명") in laws]
        
    # 공통 검색 함수 호출
    return jsonify(process_search(filtered_cases, data, "판례 정보"))

@app.route("/criminal/laws", methods=["GET"])
def get_criminal_laws():
    return jsonify(criminal_all_laws)

@app.route("/criminal/articles", methods=["GET"])
def get_criminal_articles():
    law = request.args.get("law", "").strip()
    if not law or law not in criminal_laws_dict:
        return jsonify([])
    return jsonify(criminal_laws_dict[law])

@app.route("/criminal/search", methods=["POST"])
def search_criminal_cases():
    """형사 판례 검색 API"""
    data = request.json
    selected_law = data.get("selectedLaw", "").strip()
    selected_article = data.get("selectedArticle", "").strip()

    # 형사 판례에만 해당하는 '참조조문' 필터링 로직
    filtered_rows = criminal_rows
    if selected_law:
        # comprehension을 사용하여 더 간결하게 필터링
        filtered_rows = [row for row in filtered_rows if selected_law in row.get("참조조문", "")]
    if selected_article:
        # 이미 selected_law로 필터링된 결과에 대해 추가 필터링
        filtered_rows = [row for row in filtered_rows if selected_article in row.get("참조조문", "")]
    # 공통 검색 함수 호출
    return jsonify(process_search(filtered_rows, data, "선고일자"))

# --- [수정] 회원/인증 (SQLite 연동) ---
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    nickname = data.get("nickname", "").strip()
    password = data.get("password", "").strip()
    if not nickname or not password:
        return jsonify({"error": "닉네임과 비밀번호를 모두 입력하세요."}), 400

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE nickname = ?", (nickname,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "이미 존재하는 닉네임입니다."}), 400

    hashed_password = generate_password_hash(password)
    cursor.execute("INSERT INTO users (nickname, password, bookmarks) VALUES (?, ?, ?)",
                   (nickname, hashed_password, json.dumps([])))
    conn.commit()
    conn.close()
    return jsonify({"message": "회원가입이 완료되었습니다."})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    nickname = data.get("nickname", "").strip()
    password = data.get("password", "").strip()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE nickname = ?", (nickname,))
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user[0], password):
        return jsonify({"error": "닉네임 또는 비밀번호가 올바르지 않습니다."}), 400

    session["nickname"] = nickname
    return jsonify({"message": "로그인 성공"})

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("nickname", None)
    return jsonify({"message": "로그아웃 완료"})

@app.route("/whoami")
def whoami():
    if "nickname" not in session:
        return jsonify({})

    nickname = session["nickname"]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT bookmarks FROM users WHERE nickname = ?", (nickname,))
    user = cursor.fetchone()
    conn.close()

    bookmarks = json.loads(user[0]) if user else []
    return jsonify({"nickname": nickname, "bookmarks": bookmarks})

# --- [수정] 북마크 (SQLite 연동) ---
@app.route("/bookmarks/add", methods=["POST"])
def add_bookmark():
    if "nickname" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    nickname = session["nickname"]
    new_bookmark = {"제목": request.json["제목"], "type": request.json["type"]}

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT bookmarks FROM users WHERE nickname = ?", (nickname,))
    user = cursor.fetchone()
    bookmarks = json.loads(user[0]) if user else []

    if new_bookmark not in bookmarks:
        bookmarks.append(new_bookmark)
        cursor.execute("UPDATE users SET bookmarks = ? WHERE nickname = ?", (json.dumps(bookmarks), nickname))
        conn.commit()

    conn.close()
    return jsonify({"status": "added", "bookmarks": bookmarks})

@app.route("/bookmarks/remove", methods=["POST"])
def remove_bookmark():
    if "nickname" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    nickname = session["nickname"]
    bookmark_to_remove = {"제목": request.json["제목"], "type": request.json["type"]}

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT bookmarks FROM users WHERE nickname = ?", (nickname,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "사용자 정보를 찾을 수 없습니다."}), 404

    bookmarks = json.loads(user[0])
    new_bookmarks = [bm for bm in bookmarks if bm != bookmark_to_remove]

    if len(new_bookmarks) < len(bookmarks):
        cursor.execute("UPDATE users SET bookmarks = ? WHERE nickname = ?", (json.dumps(new_bookmarks), nickname))
        conn.commit()

    conn.close()
    return jsonify({"status": "removed", "bookmarks": new_bookmarks})

@app.route("/bookmarks")
def get_bookmarks():
    if "nickname" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    nickname = session["nickname"]
    
    # [수정] DB에서 북마크 데이터를 가져옵니다.
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT bookmarks FROM users WHERE nickname = ?", (nickname,))
    user = cursor.fetchone()
    conn.close()

    # DB에서 가져온 JSON 문자열을 파이썬 리스트로 변환합니다.
    bookmarks = json.loads(user[0]) if user else []

    # --- 이하 로직은 기존과 동일합니다 ---
    btype = request.args.get("type", "all")
    legacy_page = int(request.args.get("legacy_page", 1))
    criminal_page = int(request.args.get("criminal_page", 1))
    page_size = 10

    legacy_bookmarks = []
    criminal_bookmarks = []

    for bm in bookmarks:
        if bm["type"] == "legacy":
            match = next((c for c in CASES if c.get("제목") == bm["제목"]), None)
            if match:
                legacy_bookmarks.append({**match, "type": "legacy"})
        elif bm["type"] == "criminal":
            match = next((c for c in criminal_rows if c.get("제목") == bm["제목"]), None)
            if match:
                criminal_bookmarks.append({**match, "type": "criminal"})
    
    response = {}
    
    if btype == "all" or btype == "legacy":
        legacy_total = len(legacy_bookmarks)
        legacy_start = (legacy_page - 1) * page_size
        legacy_end = legacy_start + page_size
        response["legacy"] = {
            "results": legacy_bookmarks[legacy_start:legacy_end],
            "total": legacy_total,
            "page": legacy_page,
            "pageSize": page_size
        }

    if btype == "all" or btype == "criminal":
        criminal_total = len(criminal_bookmarks)
        criminal_start = (criminal_page - 1) * page_size
        criminal_end = criminal_start + page_size
        response["criminal"] = {
            "results": criminal_bookmarks[criminal_start:criminal_end],
            "total": criminal_total,
            "page": criminal_page,
            "pageSize": page_size
        }
        
    return jsonify(response)

if __name__ == "__main__":
    init_db()  # <<<<<<<<<<< [추가] 앱 실행 시 데이터베이스 파일 생성
    app.run(debug=True)