import os, tempfile, unittest, sqlite3
from datetime import date, timedelta
os.environ["LIBRARY_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import app as A

class T(unittest.TestCase):
    def setUp(self):
        if os.path.exists(A.DB): os.remove(A.DB)
        A.init(); self.c = A.app.test_client()
    def book(self, isbn="1234567890"):
        return self.c.post("/api/books", json={"title": "T", "author": "A", "isbn": isbn})
    def test_add_and_search(self):
        self.assertEqual(self.book().status_code, 201)
        self.assertEqual(len(self.c.get("/api/books?q=Clean").json), 1)
    def test_duplicate_isbn(self): self.book(); self.assertEqual(self.book().status_code, 409)
    def test_bad_isbn(self): self.assertEqual(self.book("12").status_code, 400)
    def test_search_nonexistent(self): self.assertEqual(self.c.get("/api/books?q=zzzz").json, [])
    def test_issue_twice(self):
        self.assertEqual(self.c.post("/api/books/1/issue", json={"member_id": 1}).status_code, 200)
        self.assertEqual(self.c.post("/api/books/1/issue", json={"member_id": 2}).status_code, 409)
    def test_return_not_issued(self): self.assertEqual(self.c.post("/api/books/1/return").status_code, 409)
    def test_delete_issued(self):
        self.c.post("/api/books/1/issue", json={"member_id": 1})
        self.assertEqual(self.c.delete("/api/books/1").status_code, 409)
    def test_missing_book(self): self.assertEqual(self.c.post("/api/books/99/return").status_code, 404)
    def test_member_limit(self):
        for i in (1, 2, 3): self.c.post(f"/api/books/{i}/issue", json={"member_id": 1})
        self.assertEqual(self.c.post("/api/books/4/issue", json={"member_id": 1}).status_code, 409)
    def test_fine(self):
        self.c.post("/api/books/1/issue", json={"member_id": 1})
        old = (date.today() - timedelta(days=20)).isoformat()
        x = sqlite3.connect(A.DB); x.execute("UPDATE transactions SET due_on=?", (old,)); x.commit(); x.close()
        r = self.c.post("/api/books/1/return").json
        self.assertEqual((r["days_late"], r["fine"]), (20, 100))
    def test_member_validation(self):
        self.assertEqual(self.c.post("/api/members", json={"name": "X", "email": "bad", "phone": "9876543210"}).status_code, 400)
        self.assertEqual(self.c.post("/api/members", json={"name": "X", "email": "x@y.com", "phone": "123"}).status_code, 400)

if __name__ == "__main__": unittest.main()
