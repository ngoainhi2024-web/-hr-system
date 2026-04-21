from flask import Flask, request, render_template, redirect, session, send_file
import sqlite3
import pandas as pd
from urllib.parse import unquote

app = Flask(__name__)
app.secret_key = "secret123"

# ===== LOGIN =====
USER = "admin"
PASS = "123"

# ===== DB =====
def init_db():
    conn = sqlite3.connect("hr.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS bang_luong (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ten TEXT,
        thang TEXT,
        luong REAL,
        thuong REAL,
        phu_cap REAL,
        nguoi_pt REAL,
        tong REAL,
        thue REAL,
        thuc_nhan REAL,
        UNIQUE(ten, thang)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ===== HÀM =====
def safe(x):
    try: return float(x)
    except: return 0

def tinh_thue(x):
    if x <= 5000000: return x*0.05
    elif x <= 10000000: return 250000+(x-5000000)*0.1
    elif x <= 18000000: return 750000+(x-10000000)*0.15
    elif x <= 32000000: return 1950000+(x-18000000)*0.2
    elif x <= 52000000: return 4750000+(x-32000000)*0.25
    elif x <= 80000000: return 9750000+(x-52000000)*0.3
    else: return 18150000+(x-80000000)*0.35

def calc(luong, thuong, phu_cap, nguoi_pt):
    tong = luong + thuong + phu_cap
    bh = tong * 0.105
    giam_tru = 11000000 + nguoi_pt * 4400000
    tn = max(0, tong - bh - giam_tru)
    thue = tinh_thue(tn)
    thuc = tong - bh - thue
    return tong, thue, thuc

def check_login():
    return "user" in session

# ===== LOGIN =====
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form["user"] == USER and request.form["pass"] == PASS:
            session["user"] = USER
            return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ===== MAIN =====
@app.route("/")
def index():
    if not check_login(): return redirect("/login")

    conn = sqlite3.connect("hr.db")
    c = conn.cursor()
    c.execute("SELECT * FROM bang_luong ORDER BY ten, thang")
    data = c.fetchall()
    conn.close()

    return render_template("bangluong.html", data=data)

# ===== SAVE =====
@app.route("/save", methods=["POST"])
def save():
    if not check_login(): return redirect("/login")

    ten = request.form.get("ten")
    thang = request.form.get("thang")

    luong = safe(request.form.get("luong"))
    thuong = safe(request.form.get("thuong"))
    phu_cap = safe(request.form.get("phu_cap"))
    nguoi_pt = safe(request.form.get("nguoi_pt"))

    tong, thue, thuc = calc(luong, thuong, phu_cap, nguoi_pt)

    conn = sqlite3.connect("hr.db")
    c = conn.cursor()

    c.execute("""
    INSERT INTO bang_luong 
    (ten, thang, luong, thuong, phu_cap, nguoi_pt, tong, thue, thuc_nhan)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(ten, thang)
    DO UPDATE SET
        luong=excluded.luong,
        thuong=excluded.thuong,
        phu_cap=excluded.phu_cap,
        nguoi_pt=excluded.nguoi_pt,
        tong=excluded.tong,
        thue=excluded.thue,
        thuc_nhan=excluded.thuc_nhan
    """, (ten, thang, luong, thuong, phu_cap, nguoi_pt, tong, thue, thuc))

    conn.commit()
    conn.close()

    return redirect("/")

# ===== DELETE =====
@app.route("/delete/<int:id>")
def delete(id):
    if not check_login(): return redirect("/login")

    conn = sqlite3.connect("hr.db")
    c = conn.cursor()
    c.execute("DELETE FROM bang_luong WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

# ===== UPLOAD =====
@app.route("/upload", methods=["POST"])
def upload():
    if not check_login(): return redirect("/login")

    file = request.files["file"]
    thang = request.form.get("thang")

    df = pd.read_excel(file, engine="openpyxl").fillna(0)

    conn = sqlite3.connect("hr.db")
    c = conn.cursor()

    for _, row in df.iterrows():
        ten = str(row.get("Họ tên",""))

        luong = safe(row.get("Lương cơ bản"))
        thuong = safe(row.get("Thưởng"))
        phu_cap = safe(row.get("Phụ cấp"))
        nguoi_pt = safe(row.get("Người phụ thuộc"))

        tong, thue, thuc = calc(luong, thuong, phu_cap, nguoi_pt)

        c.execute("""
        INSERT INTO bang_luong 
        (ten, thang, luong, thuong, phu_cap, nguoi_pt, tong, thue, thuc_nhan)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ten, thang)
        DO UPDATE SET
            luong=excluded.luong,
            thuong=excluded.thuong,
            phu_cap=excluded.phu_cap,
            nguoi_pt=excluded.nguoi_pt,
            tong=excluded.tong,
            thue=excluded.thue,
            thuc_nhan=excluded.thuc_nhan
        """, (ten, thang, luong, thuong, phu_cap, nguoi_pt, tong, thue, thuc))

    conn.commit()
    conn.close()

    return redirect("/")

# ===== DASHBOARD =====
@app.route("/dashboard")
def dashboard():
    if not check_login(): return redirect("/login")

    conn = sqlite3.connect("hr.db")
    df = pd.read_sql_query("SELECT thang, SUM(tong) as tong FROM bang_luong GROUP BY thang", conn)
    conn.close()

    return render_template("dashboard.html",
        labels=df["thang"].tolist(),
        values=df["tong"].tolist()
    )

# ===== LỊCH SỬ (FIX 100%) =====
@app.route("/nhanvien/<path:ten>")
def lichsu(ten):
    if not check_login(): return redirect("/login")

    ten = unquote(ten)

    conn = sqlite3.connect("hr.db")
    c = conn.cursor()

    c.execute("""
    SELECT thang, tong, thue, thuc_nhan
    FROM bang_luong
    WHERE ten=?
    ORDER BY thang
    """, (ten,))

    data = c.fetchall()
    conn.close()

    return render_template("lichsu.html", data=data, ten=ten)

# ===== EXPORT =====
@app.route("/export")
def export():
    if not check_login(): return redirect("/login")

    conn = sqlite3.connect("hr.db")
    df = pd.read_sql_query("SELECT * FROM bang_luong", conn)
    conn.close()

    file = "bangluong.xlsx"
    df.to_excel(file, index=False)

    return send_file(file, as_attachment=True)

# ===== RUN =====
if __name__ == "__main__":
    app.run(debug=True)