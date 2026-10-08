# Library Management System

**Aim:** To design and develop a Library Management System web application that enables users to add, search, issue, return, and delete book records, using HTML, CSS, and JavaScript on the client side, Python Flask as the backend server, and SQLite for persistent storage of book and member information.

## Run
```
npm run setup     # or: pip install flask
npm start         # or: python app.py   ->  http://127.0.0.1:5000
npm test          # or: python test_app.py -v   (11 automated tests)
```

## Architecture
Browser (HTML/CSS/JS, Fetch API, JSON)  <-->  Flask REST API (app.py)  <-->  SQLite (library.db)

## Database schema
| Table | Columns |
|---|---|
| books | id PK, title, author, isbn UNIQUE, category, available |
| members | id PK, name, email UNIQUE, phone |
| transactions | id PK, book_id FK->books, member_id FK->members, issued_on, due_on, returned_on, fine |

Relationships: one member -> many transactions; one book -> many transactions.

## REST API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/books?q=&status= | List / search books |
| POST | /api/books | Add book |
| PUT | /api/books/<id> | Update book |
| DELETE | /api/books/<id> | Delete book |
| POST | /api/books/<id>/issue | Issue to member (14-day due date) |
| POST | /api/books/<id>/return | Return book (fine = Rs 5/day late) |
| GET/POST | /api/members | List / add members |
| GET | /api/history, /api/stats | Transactions, dashboard counts |

## Objectives -> Implementation
| Objective | Where |
|---|---|
| User-friendly frontend for book details | static/index.html (dashboard, tabs, forms, table) |
| RESTful endpoints (add, list, search, issue, return, delete) | app.py |
| Related tables for Books and Members | `init()` in app.py |
| Frontend-backend via HTTP + JSON | `api()` helper using Fetch |
| Cannot issue an unavailable book | `issue()` returns 409 |
| Dynamic updates without reload | `refresh()` re-renders via Fetch |
| Edge cases tested | test_app.py |
| Full-stack architecture with Node.js tooling | package.json npm scripts |

## Validation rules
ISBN 10/13 digits and unique; email format and unique; 10-digit Indian mobile; max 3 books per member; cannot delete an issued book; cannot return a book that is not issued.

## Test cases (test_app.py)
Add and search, duplicate ISBN, invalid ISBN, search non-existent book, issue already-issued book, return book not issued, delete issued book, operate on missing book (404), member borrow limit, late-return fine calculation, member field validation.
