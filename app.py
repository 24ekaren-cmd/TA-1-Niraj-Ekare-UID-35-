"""Library Management System - Flask REST API + SQLite."""
import os, re, sqlite3
from datetime import date, timedelta
from flask import Flask, jsonify, request, g

app = Flask(__name__, static_folder="static", static_url_path="")
DB = os.environ.get("LIBRARY_DB", "library.db")
LOAN_DAYS, FINE_PER_DAY, MAX_BOOKS = 14, 5, 3

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS members(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS books(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, author TEXT NOT NULL,
        isbn TEXT UNIQUE NOT NULL, category TEXT,
        available INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
        member_id INTEGER NOT NULL REFERENCES members(id),
        issued_on TEXT NOT NULL, due_on TEXT NOT NULL,
        returned_on TEXT, fine INTEGER NOT NULL DEFAULT 0);
    """)
    if not c.execute("SELECT 1 FROM books").fetchone():
        c.executemany("INSERT INTO books(title,author,isbn,category) VALUES(?,?,?,?)", [
            ("Introduction to Algorithms", "Thomas H. Cormen", "9780262033848", "Computer Science"),
            ("Clean Code", "Robert C. Martin", "9780132350884", "Software Engineering"),
            ("Database System Concepts", "Silberschatz", "9780078022159", "Databases"),
            ("Wings of Fire", "A. P. J. Abdul Kalam", "9788173711466", "Biography")])
        c.executemany("INSERT INTO members(name,email,phone) VALUES(?,?,?)", [
            ("Asha Patil", "asha@example.com", "9876543210"),
            ("Rahul Deshmukh", "rahul@example.com", "9123456780")])
    c.commit(); c.close()

def err(msg, code=400): return jsonify(error=msg), code
def body(): return request.get_json(silent=True) or {}
def clean_isbn(s): return re.sub(r"[-\s]", "", s)

@app.get("/")
def home(): return app.send_static_file("index.html")

# ---------- Books ----------
@app.get("/api/books")
def list_books():
    q, status = f"%{request.args.get('q','').strip()}%", request.args.get("status", "")
    sql = """SELECT b.*, m.name AS member, t.due_on, t.id AS tx_id,
             (t.due_on < date('now')) AS overdue
             FROM books b LEFT JOIN transactions t ON t.book_id=b.id AND t.returned_on IS NULL
             LEFT JOIN members m ON m.id=t.member_id
             WHERE (b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? OR b.category LIKE ?)"""
    if status == "available": sql += " AND b.available=1"
    elif status == "issued": sql += " AND b.available=0"
    rows = db().execute(sql + " ORDER BY b.id DESC", (q, q, q, q)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/books")
def add_book():
    d = body()
    title, author, category = (str(d.get(k, "")).strip() for k in ("title", "author", "category"))
    isbn = clean_isbn(str(d.get("isbn", "")))
    if not title or not author: return err("Title and author are required.")
    if not re.fullmatch(r"\d{10}|\d{13}", isbn): return err("ISBN must be 10 or 13 digits.")
    try:
        db().execute("INSERT INTO books(title,author,isbn,category) VALUES(?,?,?,?)", (title, author, isbn, category))
        db().commit()
    except sqlite3.IntegrityError:
        return err("A book with this ISBN already exists.", 409)
    return jsonify(ok=True), 201

@app.put("/api/books/<int:bid>")
def update_book(bid):
    d = body()
    title, author, category = (str(d.get(k, "")).strip() for k in ("title", "author", "category"))
    if not title or not author: return err("Title and author are required.")
    cur = db().execute("UPDATE books SET title=?,author=?,category=? WHERE id=?", (title, author, category, bid))
    db().commit()
    return jsonify(ok=True) if cur.rowcount else err("Book not found.", 404)

@app.delete("/api/books/<int:bid>")
def delete_book(bid):
    b = db().execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
    if not b: return err("Book not found.", 404)
    if not b["available"]: return err("Cannot delete a book that is currently issued.", 409)
    db().execute("DELETE FROM books WHERE id=?", (bid,)); db().commit()
    return jsonify(ok=True)

# ---------- Issue / Return ----------
@app.post("/api/books/<int:bid>/issue")
def issue(bid):
    mid = body().get("member_id")
    b = db().execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
    if not b: return err("Book not found.", 404)
    if not b["available"]: return err("Book is already issued.", 409)
    if not db().execute("SELECT 1 FROM members WHERE id=?", (mid,)).fetchone(): return err("Select a valid member.")
    n = db().execute("SELECT COUNT(*) FROM transactions WHERE member_id=? AND returned_on IS NULL", (mid,)).fetchone()[0]
    if n >= MAX_BOOKS: return err(f"Member already holds {MAX_BOOKS} books (limit reached).", 409)
    today = date.today()
    db().execute("INSERT INTO transactions(book_id,member_id,issued_on,due_on) VALUES(?,?,?,?)",
                 (bid, mid, today.isoformat(), (today + timedelta(days=LOAN_DAYS)).isoformat()))
    db().execute("UPDATE books SET available=0 WHERE id=?", (bid,)); db().commit()
    return jsonify(ok=True, due_on=(today + timedelta(days=LOAN_DAYS)).isoformat())

@app.post("/api/books/<int:bid>/return")
def return_book(bid):
    b = db().execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
    if not b: return err("Book not found.", 404)
    t = db().execute("SELECT * FROM transactions WHERE book_id=? AND returned_on IS NULL", (bid,)).fetchone()
    if b["available"] or not t: return err("This book was not issued.", 409)
    late = max(0, (date.today() - date.fromisoformat(t["due_on"])).days)
    fine = late * FINE_PER_DAY
    db().execute("UPDATE transactions SET returned_on=?, fine=? WHERE id=?", (date.today().isoformat(), fine, t["id"]))
    db().execute("UPDATE books SET available=1 WHERE id=?", (bid,)); db().commit()
    return jsonify(ok=True, fine=fine, days_late=late)

# ---------- Members, history, stats ----------
@app.get("/api/members")
def members():
    rows = db().execute("""SELECT m.*, (SELECT COUNT(*) FROM transactions t
        WHERE t.member_id=m.id AND t.returned_on IS NULL) AS holding FROM members m ORDER BY name""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/members")
def add_member():
    d = body()
    name, email, phone = (str(d.get(k, "")).strip() for k in ("name", "email", "phone"))
    if not name: return err("Name is required.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): return err("Enter a valid email address.")
    if not re.fullmatch(r"[6-9]\d{9}", phone): return err("Phone must be a valid 10-digit mobile number.")
    try:
        db().execute("INSERT INTO members(name,email,phone) VALUES(?,?,?)", (name, email, phone)); db().commit()
    except sqlite3.IntegrityError:
        return err("Email already registered.", 409)
    return jsonify(ok=True), 201

@app.get("/api/history")
def history():
    rows = db().execute("""SELECT t.*, b.title, m.name AS member FROM transactions t
        JOIN books b ON b.id=t.book_id JOIN members m ON m.id=t.member_id ORDER BY t.id DESC LIMIT 100""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/api/stats")
def stats():
    q = lambda s: db().execute(s).fetchone()[0]
    return jsonify(total=q("SELECT COUNT(*) FROM books"), available=q("SELECT COUNT(*) FROM books WHERE available=1"),
        issued=q("SELECT COUNT(*) FROM books WHERE available=0"), members=q("SELECT COUNT(*) FROM members"),
        overdue=q("SELECT COUNT(*) FROM transactions WHERE returned_on IS NULL AND due_on < date('now')"),
        fines=q("SELECT COALESCE(SUM(fine),0) FROM transactions"))

if __name__ == "__main__":
    init(); app.run(debug=True)
