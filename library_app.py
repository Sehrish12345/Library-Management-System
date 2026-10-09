from flask import Flask, render_template, request, redirect, url_for, session, flash 
from psycopg.errors import UniqueViolation

from db import connection
from datetime import datetime

app = Flask(__name__)

app.secret_key = "library-management-secret-key-change-this"
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cursor = connection.cursor()

        cursor.execute("""
            SELECT user_id, username
            FROM users
            WHERE username = %s
              AND password = %s
        """, (username, password))

        user = cursor.fetchone()
        cursor.close()

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "")
    category = request.args.get("category", "")
    author = request.args.get("author", "")

    cursor = connection.cursor()

    cursor.execute("""
        SELECT category_id, category_name
        FROM category
        ORDER BY category_name
    """)

    categories = cursor.fetchall()

    if search and category:
        cursor.execute("""
            SELECT DISTINCT
                b.book_id,
                b.title,
                b.isbn,
                b.publication_year,
                b.publisher
            FROM book b
            JOIN book_category bc
                ON b.book_id = bc.book_id
            WHERE b.title ILIKE %s
              AND bc.category_id = %s
            ORDER BY b.title
        """, (f"%{search}%", category))

    elif search:
        cursor.execute("""
            SELECT
                book_id,
                title,
                isbn,
                publication_year,
                publisher
            FROM book
            WHERE title ILIKE %s
            ORDER BY title
        """, (f"%{search}%",))

    elif category:
        cursor.execute("""
            SELECT DISTINCT
                b.book_id,
                b.title,
                b.isbn,
                b.publication_year,
                b.publisher
            FROM book b
            JOIN book_category bc
                ON b.book_id = bc.book_id
            WHERE bc.category_id = %s
            ORDER BY b.title
        """, (category,))

    else:
        cursor.execute("""
            SELECT
                book_id,
                title,
                isbn,
                publication_year,
                publisher
            FROM book
            ORDER BY title
        """)

    books = cursor.fetchall()

    cursor.close()

    return render_template(
        "home.html",
        books=books,
        search=search,
        categories=categories,
        selected_category=category
    )

@app.route("/book/<int:book_id>")
def book_details(book_id):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            b.book_id,
            b.title,
            b.isbn,
            b.publication_year,
            b.publisher,

            COALESCE(
                STRING_AGG(
                    DISTINCT a.author_name,
                    ', ' ORDER BY a.author_name
                ),
                'No author assigned'
            ) AS authors,

            COALESCE(
                STRING_AGG(
                    DISTINCT c.category_name,
                    ', ' ORDER BY c.category_name
                ),
                'No category assigned'
            ) AS categories

        FROM book b

        LEFT JOIN book_author ba
            ON b.book_id = ba.book_id

        LEFT JOIN author a
            ON ba.author_id = a.author_id

        LEFT JOIN book_category bc
            ON b.book_id = bc.book_id

        LEFT JOIN category c
            ON bc.category_id = c.category_id

        WHERE b.book_id = %s

        GROUP BY
            b.book_id,
            b.title,
            b.isbn,
            b.publication_year,
            b.publisher

    """, (book_id,))

    book = cursor.fetchone()
    cursor.close()

    return render_template(
        "book_details.html",
        book=book
    )


@app.route("/assign-category/<int:book_id>", methods=["GET", "POST"])
def assign_category(book_id):
    cursor = connection.cursor()

    if request.method == "POST":
        category_id = request.form["category_id"]

        cursor.execute("""
            SELECT 1
            FROM book_category
            WHERE book_id = %s
              AND category_id = %s
        """, (book_id, category_id))

        already_exists = cursor.fetchone()

        if not already_exists:
            cursor.execute("""
                INSERT INTO book_category (book_id, category_id)
                VALUES (%s, %s)
            """, (book_id, category_id))

            connection.commit()

        cursor.close()

        return redirect(
            url_for("book_details", book_id=book_id)
        )

    cursor.execute("""
        SELECT category_id, category_name
        FROM category
        ORDER BY category_name
    """)

    categories = cursor.fetchall()

    cursor.close()

    return render_template(
        "assign_category.html",
        book_id=book_id,
        categories=categories
    )

@app.route("/assign-author/<int:book_id>", methods=["GET", "POST"])
def assign_author(book_id):
    cursor = connection.cursor()

    if request.method == "POST":
        author_id = request.form["author_id"]

        cursor.execute("""
            SELECT 1
            FROM book_author
            WHERE book_id = %s
              AND author_id = %s
        """, (book_id, author_id))

        already_exists = cursor.fetchone()

        if not already_exists:
            cursor.execute("""
                INSERT INTO book_author (book_id, author_id)
                VALUES (%s, %s)
            """, (book_id, author_id))

            connection.commit()

        cursor.close()

        return redirect(
            url_for("book_details", book_id=book_id)
        )

    cursor.execute("""
        SELECT author_id, author_name
        FROM author
        ORDER BY author_name
    """)

    authors = cursor.fetchall()

    cursor.close()

    return render_template(
        "assign_author.html",
        book_id=book_id,
        authors=authors
    )

@app.route("/add-book", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":

        cursor = connection.cursor()

        try:
            title = request.form["title"]
            isbn = request.form["isbn"]
            publication_year = request.form["publication_year"]
            publisher = request.form["publisher"]
            author_name = request.form["author"].strip()
            category_name = request.form["category"].strip()

            if publication_year and int(publication_year) < 1000:
                return render_template(
                    "add_book.html",
                    error="Publication Year must be 1000 or greater.",
                    title=title,
                    isbn=isbn,
                    publication_year=publication_year,
                    publisher=publisher,
                    authors=[],
                    categories=[]
                )

            if not author_name:
                return render_template(
                    "add_book.html",
                    error="Please select or enter an author.",
                    title=title,
                    isbn=isbn,
                    publication_year=publication_year,
                    publisher=publisher,
                    authors=[],
                    categories=[]
                )

            if not category_name:
                return render_template(
                    "add_book.html",
                    error="Please select or enter a category.",
                    title=title,
                    isbn=isbn,
                    publication_year=publication_year,
                    publisher=publisher,
                    authors=[],
                    categories=[]
                )

            # Add the book first
            cursor.execute("""
                INSERT INTO book
                (title, isbn, publication_year, publisher)
                VALUES (%s, %s, %s, %s)
                RETURNING book_id
            """, (
                title,
                isbn,
                publication_year,
                publisher
            ))

            book_id = cursor.fetchone()[0]

            # Find existing author
            cursor.execute("""
                SELECT author_id
                FROM author
                WHERE author_name = %s
            """, (author_name,))

            author = cursor.fetchone()

            if author:
                author_id = author[0]

            else:
                # Create new author
                cursor.execute("""
                    INSERT INTO author (author_name)
                    VALUES (%s)
                    RETURNING author_id
                """, (author_name,))

                author_id = cursor.fetchone()[0]

            # Connect author with book
            cursor.execute("""
                INSERT INTO book_author
                (book_id, author_id)
                VALUES (%s, %s)
            """, (
                book_id,
                author_id
            ))

            # Find existing category
            cursor.execute("""
                SELECT category_id
                FROM category
                WHERE category_name = %s
            """, (category_name,))

            category = cursor.fetchone()

            if category:
                category_id = category[0]

            else:
                # Create new category
                cursor.execute("""
                    INSERT INTO category (category_name)
                    VALUES (%s)
                    RETURNING category_id
                """, (category_name,))

                category_id = cursor.fetchone()[0]

            # Connect category with book
            cursor.execute("""
                INSERT INTO book_category
                (book_id, category_id)
                VALUES (%s, %s)
            """, (
                book_id,
                category_id
            ))

            connection.commit()

            flash("Book added successfully!", "success")

        except UniqueViolation:
            connection.rollback()

            return render_template(
                "add_book.html",
                error="This ISBN, author, or category already exists. Please check your entries.",
                title=title,
                isbn=isbn,
                publication_year=publication_year,
                publisher=publisher,
                authors=[],
                categories=[]
            )

        except Exception as e:
            connection.rollback()
            print("ERROR:", e)

            return render_template(
                "add_book.html",
                error="Unable to add book. Please check the entered data.",
                title=title,
                isbn=isbn,
                publication_year=publication_year,
                publisher=publisher,
                authors=[],
                categories=[]
            )

        finally:
            cursor.close()

        return redirect("/")

    cursor = connection.cursor()

    cursor.execute("""
        SELECT author_id, author_name
        FROM author
        ORDER BY author_name
    """)

    authors = cursor.fetchall()

    cursor.execute("""
        SELECT category_id, category_name
        FROM category
        ORDER BY category_name
    """)

    categories = cursor.fetchall()

    cursor.close()

    return render_template(
        "add_book.html",
        authors=authors,
        categories=categories
    )
@app.route("/edit-book/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    cursor = connection.cursor()

    if request.method == "POST":
        title = request.form["title"]
        isbn = request.form["isbn"]
        publication_year = request.form["publication_year"]
        publisher = request.form["publisher"]
        author_name = request.form["author"].strip()
        category_name = request.form["category"].strip()

        try:
            if publication_year and int(publication_year) < 1000:
                raise ValueError("Publication Year must be 1000 or greater.")

            if not author_name:
                raise ValueError("Please select or enter an author.")

            if not category_name:
                raise ValueError("Please select or enter a category.")

            # Update basic book information
            cursor.execute("""
                UPDATE book
                SET title = %s,
                    isbn = %s,
                    publication_year = %s,
                    publisher = %s
                WHERE book_id = %s
            """, (
                title,
                isbn,
                publication_year,
                publisher,
                book_id
            ))

            # Find existing author
            cursor.execute("""
                SELECT author_id
                FROM author
                WHERE author_name = %s
            """, (author_name,))

            author = cursor.fetchone()

            if author:
                author_id = author[0]
            else:
                # Create new author
                cursor.execute("""
                    INSERT INTO author (author_name)
                    VALUES (%s)
                    RETURNING author_id
                """, (author_name,))

                author_id = cursor.fetchone()[0]

            # Replace book's author
            cursor.execute("""
                DELETE FROM book_author
                WHERE book_id = %s
            """, (book_id,))

            cursor.execute("""
                INSERT INTO book_author
                (book_id, author_id)
                VALUES (%s, %s)
            """, (
                book_id,
                author_id
            ))

            # Find existing category
            cursor.execute("""
                SELECT category_id
                FROM category
                WHERE category_name = %s
            """, (category_name,))

            category = cursor.fetchone()

            if category:
                category_id = category[0]
            else:
                # Create new category
                cursor.execute("""
                    INSERT INTO category (category_name)
                    VALUES (%s)
                    RETURNING category_id
                """, (category_name,))

                category_id = cursor.fetchone()[0]

            # Replace book's category
            cursor.execute("""
                DELETE FROM book_category
                WHERE book_id = %s
            """, (book_id,))

            cursor.execute("""
                INSERT INTO book_category
                (book_id, category_id)
                VALUES (%s, %s)
            """, (
                book_id,
                category_id
            ))

            connection.commit()

            flash("Book updated successfully!", "success")

            return redirect("/")

        except ValueError as e:
            connection.rollback()

            return render_template(
                "edit_book.html",
                error=str(e),
                book=(book_id, title, isbn, publication_year, publisher,
                      author_name, category_name),
                authors=[],
                categories=[]
            )

        except Exception as e:
            connection.rollback()
            print("EDIT BOOK ERROR:", e)

            return render_template(
                "edit_book.html",
                error="Unable to update book. Please check the entered data.",
                book=(book_id, title, isbn, publication_year, publisher,
                      author_name, category_name),
                authors=[],
                categories=[]
            )

    # Get current book details
    cursor.execute("""
        SELECT
            b.book_id,
            b.title,
            b.isbn,
            b.publication_year,
            b.publisher,
            COALESCE(a.author_name, '') AS author_name,
            COALESCE(c.category_name, '') AS category_name
        FROM book b
        LEFT JOIN book_author ba
            ON b.book_id = ba.book_id
        LEFT JOIN author a
            ON ba.author_id = a.author_id
        LEFT JOIN book_category bc
            ON b.book_id = bc.book_id
        LEFT JOIN category c
            ON bc.category_id = c.category_id
        WHERE b.book_id = %s
    """, (book_id,))

    book = cursor.fetchone()

    # Get authors
    cursor.execute("""
        SELECT author_id, author_name
        FROM author
        ORDER BY author_name
    """)

    authors = cursor.fetchall()

    # Get categories
    cursor.execute("""
        SELECT category_id, category_name
        FROM category
        ORDER BY category_name
    """)

    categories = cursor.fetchall()

    cursor.close()

    return render_template(
        "edit_book.html",
        book=book,
        authors=authors,
        categories=categories
    )


@app.route("/delete-book/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    cursor = connection.cursor()

    try:
        # Delete book-author relationship
        cursor.execute("""
            DELETE FROM book_author
            WHERE book_id = %s
        """, (book_id,))

        # Delete book-category relationship
        cursor.execute("""
            DELETE FROM book_category
            WHERE book_id = %s
        """, (book_id,))

        # Delete book copies
        cursor.execute("""
            DELETE FROM book_copy
            WHERE book_id = %s
        """, (book_id,))

        # Finally delete the book
        cursor.execute("""
            DELETE FROM book
            WHERE book_id = %s
        """, (book_id,))

        connection.commit()

        flash("Book deleted successfully!", "success")

    except Exception as e:
        connection.rollback()
        print("DELETE BOOK ERROR:", e)

    finally:
        cursor.close()

    return redirect("/")


@app.route("/authors")
def authors():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT author_id, author_name
        FROM author
        ORDER BY author_id
    """)

    authors = cursor.fetchall()
    cursor.close()

    return render_template("authors.html", authors=authors)

@app.route("/add-author", methods=["GET", "POST"])
def add_author():
    if request.method == "POST":
        author_name = request.form["author_name"]

        # connection.rollback()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO author (author_name)
            VALUES (%s)
        """, (author_name,))

        connection.commit()
        cursor.close()

        return redirect("/authors")

    return render_template("add_author.html")

@app.route("/edit-author/<int:author_id>", methods=["GET", "POST"])
def edit_author(author_id):
    cursor = connection.cursor()

    if request.method == "POST":
        author_name = request.form["author_name"]

        cursor.execute("""
            UPDATE author
            SET author_name = %s
            WHERE author_id = %s
        """, (author_name, author_id))

        connection.commit()
        cursor.close()

        return redirect("/authors")

    cursor.execute("""
        SELECT author_id, author_name
        FROM author
        WHERE author_id = %s
    """, (author_id,))

    author = cursor.fetchone()
    cursor.close()

    return render_template("edit_author.html", author=author)

@app.route("/delete-author/<int:author_id>", methods=["POST"])
def delete_author(author_id):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM book_author
        WHERE author_id = %s
    """, (author_id,))

    count = cursor.fetchone()[0]

    if count > 0:
        cursor.close()
        return redirect("/authors")

    cursor.execute("""
        DELETE FROM author
        WHERE author_id = %s
    """, (author_id,))

    connection.commit()
    cursor.close()

    return redirect("/authors")

@app.route("/categories")
def categories():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT category_id, category_name
        FROM category
        ORDER BY category_id
    """)

    categories = cursor.fetchall()
    cursor.close()

    return render_template("categories.html", categories=categories)

@app.route("/add-category", methods=["GET", "POST"])
def add_category():
    if request.method == "POST":
        category_name = request.form["category_name"]

        # connection.rollback()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO category (category_name)
            VALUES (%s)
        """, (category_name,))

        connection.commit()
        cursor.close()

        return redirect("/categories")

    return render_template("add_category.html")

@app.route("/edit-category/<int:category_id>", methods=["GET", "POST"])
def edit_category(category_id):
    cursor = connection.cursor()

    if request.method == "POST":
        category_name = request.form["category_name"]

        cursor.execute("""
            UPDATE category
            SET category_name = %s
            WHERE category_id = %s
        """, (category_name, category_id))

        connection.commit()
        cursor.close()

        return redirect("/categories")

    cursor.execute("""
        SELECT category_id, category_name
        FROM category
        WHERE category_id = %s
    """, (category_id,))

    category = cursor.fetchone()
    cursor.close()

    return render_template("edit_category.html", category=category)

@app.route("/delete-category/<int:category_id>", methods=["POST"])
def delete_category(category_id):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM book_category
        WHERE category_id = %s
    """, (category_id,))

    count = cursor.fetchone()[0]

    if count > 0:
        cursor.close()
        return redirect("/categories")

    cursor.execute("""
        DELETE FROM category
        WHERE category_id = %s
    """, (category_id,))

    connection.commit()
    cursor.close()

    return redirect("/categories")

@app.route("/members")
def members():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT member_id,
               member_name,
               email,
               phone,
               address,
               registration_date,
               membership_status
        FROM member
        ORDER BY member_id
    """)

    members = cursor.fetchall()
    cursor.close()

    return render_template("members.html", members=members)

@app.route("/add-member", methods=["GET", "POST"])
def add_member():
    if request.method == "POST":
        member_name = request.form["member_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        registration_date = request.form["registration_date"]
        membership_status = request.form["membership_status"]

        # connection.rollback()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO member
            (member_name, email, phone, address, registration_date, membership_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            member_name,
            email,
            phone,
            address,
            registration_date,
            membership_status
        ))

        connection.commit()
        cursor.close()

        return redirect("/members")

    return render_template("add_member.html")

@app.route("/edit-member/<int:member_id>", methods=["GET", "POST"])
def edit_member(member_id):
    cursor = connection.cursor()

    if request.method == "POST":
        member_name = request.form["member_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        registration_date = request.form["registration_date"]
        membership_status = request.form["membership_status"]

        cursor.execute("""
            UPDATE member
            SET member_name = %s,
                email = %s,
                phone = %s,
                address = %s,
                registration_date = %s,
                membership_status = %s
            WHERE member_id = %s
        """, (
            member_name,
            email,
            phone,
            address,
            registration_date,
            membership_status,
            member_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/members")

    cursor.execute("""
        SELECT member_id,
               member_name,
               email,
               phone,
               address,
               registration_date,
               membership_status
        FROM member
        WHERE member_id = %s
    """, (member_id,))

    member = cursor.fetchone()
    cursor.close()

    return render_template("edit_member.html", member=member)


@app.route("/delete-member/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    try:
        # Check existing borrowing records
        borrowing_count = connection.execute(
            "SELECT COUNT(*) FROM borrowing WHERE member_id = %s",
            (member_id,)
        ).fetchone()[0]

        if borrowing_count > 0:
            flash(
                "Cannot delete member: This member has existing borrowing records.",
                "error"
            )
            return redirect(url_for("members"))

        # Check existing request records
        request_count = connection.execute(
            "SELECT COUNT(*) FROM request WHERE member_id = %s",
            (member_id,)
        ).fetchone()[0]

        if request_count > 0:
            flash(
                "Cannot delete member: This member has existing requests.",
                "error"
            )
            return redirect(url_for("members"))

        # Check existing account records
        account_count = connection.execute(
            "SELECT COUNT(*) FROM account WHERE member_id = %s",
            (member_id,)
        ).fetchone()[0]

        if account_count > 0:
            flash(
                "Cannot delete member: This member has existing account records.",
                "error"
            )
            return redirect(url_for("members"))

        # Delete member if no related records exist
        connection.execute(
            "DELETE FROM member WHERE member_id = %s",
            (member_id,)
        )
        connection.commit()

        flash("Member deleted successfully.", "success")

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred while deleting the member: {e}", "error")

    return redirect(url_for("members"))

@app.route("/branches")
def branches():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT branch_id,
               branch_name,
               address,
               opening_days,
               opening_time,
               closing_time
        FROM branches
        ORDER BY branch_id
    """)

    branches = cursor.fetchall()
    cursor.close()

    return render_template("branches.html", branches=branches)

@app.route("/add-branch", methods=["GET", "POST"])
def add_branch():
    if request.method == "POST":
        branch_name = request.form["branch_name"]
        address = request.form["address"]
        opening_days = request.form["opening_days"]
        opening_time = request.form["opening_time"]
        closing_time = request.form["closing_time"]

        # connection.rollback()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO branches
            (branch_name, address, opening_days, opening_time, closing_time)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            branch_name,
            address,
            opening_days,
            opening_time,
            closing_time
        ))

        connection.commit()
        cursor.close()

        return redirect("/branches")

    return render_template("add_branch.html")

@app.route("/edit-branch/<int:branch_id>", methods=["GET", "POST"])
def edit_branch(branch_id):
    cursor = connection.cursor()

    if request.method == "POST":
        branch_name = request.form["branch_name"]
        address = request.form["address"]
        opening_days = request.form["opening_days"]
        opening_time = request.form["opening_time"]
        closing_time = request.form["closing_time"]

        cursor.execute("""
            UPDATE branches
            SET branch_name = %s,
                address = %s,
                opening_days = %s,
                opening_time = %s,
                closing_time = %s
            WHERE branch_id = %s
        """, (
            branch_name,
            address,
            opening_days,
            opening_time,
            closing_time,
            branch_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/branches")

    cursor.execute("""
        SELECT branch_id,
               branch_name,
               address,
               opening_days,
               opening_time,
               closing_time
        FROM branches
        WHERE branch_id = %s
    """, (branch_id,))

    branch = cursor.fetchone()
    cursor.close()

    return render_template("edit_branch.html", branch=branch)

@app.route("/delete-branch/<int:branch_id>", methods=["POST"])
def delete_branch(branch_id):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM book_copy WHERE branch_id = %s),
            (SELECT COUNT(*) FROM staff WHERE branch_id = %s),
            (SELECT COUNT(*) FROM borrowing WHERE branch_id = %s)
    """, (branch_id, branch_id, branch_id))

    copy_count, staff_count, borrowing_count = cursor.fetchone()

    if copy_count > 0 or staff_count > 0 or borrowing_count > 0:
        cursor.close()
        flash("Cannot delete branch: Related book copies, staff, or borrowing records exist.",
        "error")

        return redirect("/branches")

    cursor.execute("""
        DELETE FROM branches
        WHERE branch_id = %s
    """, (branch_id,))

    connection.commit()
    flash("Branch deleted successfully.", "success")
    cursor.close()

    return redirect("/branches")

@app.route("/staff")
def staff():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT staff_id,
               staff_name,
               email,
               phone,
               job_title,
               branch_id
        FROM staff
        ORDER BY staff_id
    """)

    staff_members = cursor.fetchall()
    cursor.close()

    return render_template("staff.html", staff_members=staff_members)

@app.route("/add-staff", methods=["GET", "POST"])
def add_staff():
    if request.method == "POST":
        staff_name = request.form["staff_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        job_title = request.form["job_title"]
        branch_id = request.form["branch_id"]

        # connection.rollback()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO staff
            (staff_name, email, phone, job_title, branch_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            staff_name,
            email,
            phone,
            job_title,
            branch_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/staff")

    return render_template("add_staff.html")

@app.route("/edit-staff/<int:staff_id>", methods=["GET", "POST"])
def edit_staff(staff_id):
    cursor = connection.cursor()

    if request.method == "POST":
        staff_name = request.form["staff_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        job_title = request.form["job_title"]
        branch_id = request.form["branch_id"]

        cursor.execute("""
            UPDATE staff
            SET staff_name = %s,
                email = %s,
                phone = %s,
                job_title = %s,
                branch_id = %s
            WHERE staff_id = %s
        """, (
            staff_name,
            email,
            phone,
            job_title,
            branch_id,
            staff_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/staff")

    cursor.execute("""
        SELECT staff_id,
               staff_name,
               email,
               phone,
               job_title,
               branch_id
        FROM staff
        WHERE staff_id = %s
    """, (staff_id,))

    staff_member = cursor.fetchone()
    cursor.close()

    return render_template("edit_staff.html", staff=staff_member)

@app.route("/delete-staff/<int:staff_id>", methods=["POST"])
def delete_staff(staff_id):
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM staff
        WHERE staff_id = %s
    """, (staff_id,))

    connection.commit()
    cursor.close()

    return redirect("/staff")

@app.route("/book-copies")
def book_copies():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            bc.copy_id,
            b.title,
            br.branch_name,
            bc.status
        FROM book_copy bc
        JOIN book b
            ON bc.book_id = b.book_id
        JOIN branches br
            ON bc.branch_id = br.branch_id
        ORDER BY bc.copy_id
    """)

    copies = cursor.fetchall()
    cursor.close()

    return render_template("book_copies.html", copies=copies)

@app.route("/add-book-copy", methods=["GET", "POST"])
def add_book_copy():
    if request.method == "POST":
        book_id = request.form["book_id"]
        branch_id = request.form["branch_id"]
        status = request.form["status"]

        # connection.rollback()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO book_copy
            (book_id, branch_id, status)
            VALUES (%s, %s, %s)
        """, (
            book_id,
            branch_id,
            status
        ))

        connection.commit()
        cursor.close()

        return redirect("/book-copies")

    cursor = connection.cursor()

    cursor.execute("""
        SELECT book_id, title
        FROM book
        ORDER BY title
    """)
    books = cursor.fetchall()

    cursor.execute("""
        SELECT branch_id, branch_name
        FROM branches
        ORDER BY branch_name
    """)
    branches = cursor.fetchall()

    cursor.close()

    return render_template(
        "add_book_copy.html",
        books=books,
        branches=branches
    )

@app.route("/edit-book-copy/<int:copy_id>", methods=["GET", "POST"])
def edit_book_copy(copy_id):
    cursor = connection.cursor()

    if request.method == "POST":
        book_id = request.form["book_id"]
        branch_id = request.form["branch_id"]
        status = request.form["status"]

        cursor.execute("""
            UPDATE book_copy
            SET book_id = %s,
                branch_id = %s,
                status = %s
            WHERE copy_id = %s
        """, (
            book_id,
            branch_id,
            status,
            copy_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/book-copies")

    cursor.execute("""
        SELECT copy_id,
               book_id,
               branch_id,
               status
        FROM book_copy
        WHERE copy_id = %s
    """, (copy_id,))

    copy = cursor.fetchone()

    cursor.execute("""
        SELECT book_id, title
        FROM book
        ORDER BY title
    """)
    books = cursor.fetchall()

    cursor.execute("""
        SELECT branch_id, branch_name
        FROM branches
        ORDER BY branch_name
    """)
    branches = cursor.fetchall()

    cursor.close()

    return render_template(
        "edit_book_copy.html",
        copy=copy,
        books=books,
        branches=branches
    )

@app.route("/delete-book-copy/<int:copy_id>", methods=["POST"])
def delete_book_copy(copy_id):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM borrowing
        WHERE copy_id = %s
    """, (copy_id,))

    borrowing_count = cursor.fetchone()[0]

    if borrowing_count > 0:
        cursor.close()
        return redirect("/book-copies")

    cursor.execute("""
        DELETE FROM book_copy
        WHERE copy_id = %s
    """, (copy_id,))

    connection.commit()
    cursor.close()

    return redirect("/book-copies")

@app.route("/borrowing")
def borrowing():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            br.borrowing_id,
            b.title,
            m.member_name,
            branches.branch_name,
            br.borrow_date,
            br.due_date,
            br.return_date
        FROM borrowing br
        JOIN book_copy bc
            ON br.copy_id = bc.copy_id
        JOIN book b
            ON bc.book_id = b.book_id
        JOIN member m
            ON br.member_id = m.member_id
        JOIN branches
            ON br.branch_id = branches.branch_id
        ORDER BY br.borrowing_id
    """)

    borrowings = cursor.fetchall()
    cursor.close()

    return render_template("borrowing.html", borrowings=borrowings)


@app.route("/add-borrowing", methods=["GET", "POST"])
def add_borrowing():
    if request.method == "POST":
        copy_id = request.form["copy_id"]
        member_id = request.form["member_id"]
        branch_id = request.form["branch_id"]
        borrow_date = request.form["borrow_date"]
        due_date = request.form["due_date"]

        cursor = connection.cursor()

        try:
            # Validate dates
            borrow = datetime.strptime(borrow_date, "%Y-%m-%d").date()
            due = datetime.strptime(due_date, "%Y-%m-%d").date()

            if due < borrow:
                flash("Due date cannot be before borrow date.", "error")
                return redirect(url_for("add_borrowing"))

            # Lock and check the selected copy
            cursor.execute("""
                SELECT status
                FROM book_copy
                WHERE copy_id = %s
                FOR UPDATE
            """, (copy_id,))

            copy = cursor.fetchone()

            if not copy or copy[0] != "Available":
                flash("This book copy is not available.", "error")
                connection.rollback()
                return redirect(url_for("add_borrowing"))

            # Check member is active
            cursor.execute("""
                SELECT member_id
                FROM member
                WHERE member_id = %s
                  AND membership_status = 'Active'
            """, (member_id,))

            if not cursor.fetchone():
                flash("Please select an active member.", "error")
                connection.rollback()
                return redirect(url_for("add_borrowing"))

            # Check branch exists
            cursor.execute("""
                SELECT branch_id
                FROM branches
                WHERE branch_id = %s
            """, (branch_id,))

            if not cursor.fetchone():
                flash("Selected branch does not exist.", "error")
                connection.rollback()
                return redirect(url_for("add_borrowing"))

            # Create borrowing record
            cursor.execute("""
                INSERT INTO borrowing
                (copy_id, member_id, branch_id, borrow_date, due_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                copy_id, member_id, branch_id,
                borrow_date, due_date
            ))

            # Mark the copy as borrowed
            cursor.execute("""
                UPDATE book_copy
                SET status = 'Borrowed'
                WHERE copy_id = %s
            """, (copy_id,))

            connection.commit()
            flash("Book issued successfully.", "success")
            return redirect(url_for("borrowing"))

        except ValueError:
            connection.rollback()
            flash("Please enter valid borrowing dates.", "error")
            return redirect(url_for("add_borrowing"))

        except Exception:
            connection.rollback()
            flash("Unable to issue book. Please check the details.", "error")
            return redirect(url_for("add_borrowing"))

        finally:
            cursor.close()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT bc.copy_id, b.title
        FROM book_copy bc
        JOIN book b ON bc.book_id = b.book_id
        WHERE bc.status = 'Available'
        ORDER BY b.title
    """)
    copies = cursor.fetchall()

    cursor.execute("""
        SELECT member_id, member_name
        FROM member
        WHERE membership_status = 'Active'
        ORDER BY member_name
    """)
    members = cursor.fetchall()

    cursor.execute("""
        SELECT branch_id, branch_name
        FROM branches
        ORDER BY branch_name
    """)
    branches = cursor.fetchall()

    cursor.close()

    return render_template(
        "add_borrowing.html",
        copies=copies,
        members=members,
        branches=branches
    )

@app.route("/edit-borrowing/<int:borrowing_id>", methods=["GET", "POST"])
def edit_borrowing(borrowing_id):
    cursor = connection.cursor()

    if request.method == "POST":
        copy_id = request.form["copy_id"]
        member_id = request.form["member_id"]
        branch_id = request.form["branch_id"]
        borrow_date = request.form["borrow_date"]
        due_date = request.form["due_date"]
        return_date = request.form["return_date"]

        cursor.execute("""
            UPDATE borrowing
            SET copy_id = %s,
                member_id = %s,
                branch_id = %s,
                borrow_date = %s,
                due_date = %s,
                return_date = %s
            WHERE borrowing_id = %s
        """, (
            copy_id,
            member_id,
            branch_id,
            borrow_date,
            due_date,
            return_date if return_date else None,
            borrowing_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/borrowing")

    cursor.execute("""
        SELECT borrowing_id,
               copy_id,
               member_id,
               branch_id,
               borrow_date,
               due_date,
               return_date
        FROM borrowing
        WHERE borrowing_id = %s
    """, (borrowing_id,))

    borrowing_record = cursor.fetchone()

    cursor.execute("""
        SELECT copy_id, b.title
        FROM book_copy bc
        JOIN book b
            ON bc.book_id = b.book_id
        ORDER BY b.title
    """)
    copies = cursor.fetchall()

    cursor.execute("""
        SELECT member_id, member_name
        FROM member
        ORDER BY member_name
    """)
    members = cursor.fetchall()

    cursor.execute("""
        SELECT branch_id, branch_name
        FROM branches
        ORDER BY branch_name
    """)
    branches = cursor.fetchall()

    cursor.close()

    return render_template(
        "edit_borrowing.html",
        borrowing=borrowing_record,
        copies=copies,
        members=members,
        branches=branches
    )

@app.route("/delete-borrowing/<int:borrowing_id>", methods=["POST"])
def delete_borrowing(borrowing_id):
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM borrowing
        WHERE borrowing_id = %s
    """, (borrowing_id,))

    connection.commit()
    flash("Borrowing record deleted successfully.", "success")

    connection.rollback()
    flash("Unable to delete borrowing record.", "error")
    cursor.close()

    return redirect("/borrowing")
@app.route("/requests")
def requests():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            r.request_id,
            b.title,
            m.member_name,
            r.request_date,
            r.status
        FROM request r
        JOIN book b
            ON r.book_id = b.book_id
        JOIN member m
            ON r.member_id = m.member_id
        ORDER BY r.request_id
    """)

    book_requests = cursor.fetchall()
    cursor.close()

    return render_template(
        "requests.html",
        book_requests=book_requests
    )

@app.route("/add-request", methods=["GET", "POST"])
def add_request():
    if request.method == "POST":
        book_id = request.form["book_id"]
        member_id = request.form["member_id"]
        request_date = request.form["request_date"]

        # Get status and handle old Pending value
        status = request.form.get("status", "Waiting").strip()

        if status == "Pending":
            status = "Waiting"

        # Validate status against database constraint
        allowed_statuses = [
            "Waiting",
            "Approved",
            "Rejected",
            "Completed"
        ]

        if status not in allowed_statuses:
            flash("Invalid request status selected.", "error")
            return redirect(url_for("add_request"))

        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO request
                (book_id, member_id, request_date, status)
                VALUES (%s, %s, %s, %s)
            """, (
                book_id,
                member_id,
                request_date,
                status
            ))

            connection.commit()
            flash("Book request added successfully.", "success")

        except Exception:
            connection.rollback()
            flash("Unable to add request. Please check the details.", "error")

        finally:
            cursor.close()

        return redirect(url_for("requests"))

    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT book_id, title
            FROM book
            ORDER BY title
        """)
        books = cursor.fetchall()

        cursor.execute("""
            SELECT member_id, member_name
            FROM member
            ORDER BY member_name
        """)
        members = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "add_request.html",
        books=books,
        members=members
    )

@app.route("/edit-request/<int:request_id>", methods=["GET", "POST"])
def edit_request(request_id):
    cursor = connection.cursor()

    if request.method == "POST":
        book_id = request.form["book_id"]
        member_id = request.form["member_id"]
        request_date = request.form["request_date"]
        status = request.form["status"]

        cursor.execute("""
            UPDATE request
            SET book_id = %s,
                member_id = %s,
                request_date = %s,
                status = %s
            WHERE request_id = %s
        """, (
            book_id,
            member_id,
            request_date,
            status,
            request_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/requests")

    cursor.execute("""
        SELECT request_id,
               book_id,
               member_id,
               request_date,
               status
        FROM request
        WHERE request_id = %s
    """, (request_id,))

    request_record = cursor.fetchone()

    cursor.execute("""
        SELECT book_id, title
        FROM book
        ORDER BY title
    """)
    books = cursor.fetchall()

    cursor.execute("""
        SELECT member_id, member_name
        FROM member
        ORDER BY member_name
    """)
    members = cursor.fetchall()

    cursor.close()

    return render_template(
        "edit_request.html",
        request_record=request_record,
        books=books,
        members=members
    )


@app.route("/delete-request/<int:request_id>", methods=["POST"])
def delete_request(request_id):
    cursor = connection.cursor()

    try:
        cursor.execute("""
            DELETE FROM request
            WHERE request_id = %s
        """, (request_id,))

        if cursor.rowcount > 0:
            connection.commit()
            flash("Request deleted successfully.", "success")
        else:
            connection.rollback()
            flash("Request not found.", "error")

    except Exception:
        connection.rollback()
        flash("Unable to delete request.", "error")

    finally:
        cursor.close()

    return redirect("/requests")


@app.route("/returns")
def returns():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            br.borrowing_id,
            b.title,
            m.member_name,
            br.borrow_date,
            br.due_date,
            br.return_date
        FROM borrowing br
        JOIN book_copy bc
            ON br.copy_id = bc.copy_id
        JOIN book b
            ON bc.book_id = b.book_id
        JOIN member m
            ON br.member_id = m.member_id
        WHERE br.return_date IS NOT NULL
        ORDER BY br.return_date DESC
    """)

    returned_books = cursor.fetchall()
    cursor.close()

    return render_template(
        "returns.html",
        returned_books=returned_books
    )
@app.route("/overdue-books")
def overdue_books():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            member_name,
            borrowing_id,
            copy_id,
            borrow_date,
            due_date
        FROM overdue_books
        ORDER BY due_date
    """)

    overdue = cursor.fetchall()
    cursor.close()

    return render_template(
        "overdue_books.html",
        overdue=overdue
    )
@app.route("/available-books")
def available_books():
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            book_title,
            copy_id,
            branch_name
        FROM available_books
        ORDER BY book_title
    """)

    available = cursor.fetchall()
    cursor.close()

    return render_template(
        "available_books.html",
        available=available
    )


@app.route("/member-accounts")
def member_accounts():
    cursor = connection.cursor()

    # Get all borrowings and calculate overdue days
    cursor.execute("""
        SELECT
            borrowing_id,
            member_id,
            GREATEST(
                COALESCE(return_date, CURRENT_DATE) - due_date,
                0
            ) AS overdue_days
        FROM borrowing
    """)

    borrowings = cursor.fetchall()

    for borrowing in borrowings:
        borrowing_id = borrowing[0]
        member_id = borrowing[1]
        overdue_days = borrowing[2]

        # Fine = Rs. 10 per overdue day
        fine_amount = overdue_days * 10

        # Check whether an account record already exists
        cursor.execute("""
            SELECT account_id, status
            FROM account
            WHERE borrowing_id = %s
            ORDER BY account_id
            LIMIT 1
        """, (borrowing_id,))

        existing_account = cursor.fetchone()

        if existing_account:
            account_id = existing_account[0]
            status = existing_account[1]

            # Update unpaid fines, but keep paid records unchanged
            if status == "Unpaid":
                cursor.execute("""
                    UPDATE account
                    SET amount = %s
                    WHERE account_id = %s
                """, (fine_amount, account_id))

        elif fine_amount > 0:
            # Add a new record only if a fine is due
            cursor.execute("""
                INSERT INTO account
                    (member_id, borrowing_id, amount,
                     transaction_date, status)
                VALUES (%s, %s, %s, CURRENT_DATE, 'Unpaid')
            """, (member_id, borrowing_id, fine_amount))

    # Save calculated fines
    connection.commit()

    # Load account records for the page
    cursor.execute("""
        SELECT
            member_name,
            account_id,
            amount,
            transaction_date,
            status
        FROM member_accounts
        ORDER BY account_id
    """)

    accounts = cursor.fetchall()
    cursor.close()

    return render_template(
        "member_accounts.html",
        accounts=accounts
    )


@app.route("/add-account", methods=["GET", "POST"])
def add_account():
    cursor = connection.cursor()

    if request.method == "POST":
        member_id = request.form["member_id"]
        borrowing_id = request.form["borrowing_id"]

        # Get borrowing details
        cursor.execute("""
            SELECT member_id, due_date, return_date
            FROM borrowing
            WHERE borrowing_id = %s
        """, (borrowing_id,))

        borrowing = cursor.fetchone()

        if not borrowing:
            cursor.close()
            return "Borrowing record not found.", 404

        actual_member_id, due_date, return_date = borrowing

        # Check that the borrowing belongs to this member
        if str(actual_member_id) != str(member_id):
            cursor.close()
            return "Member and borrowing do not match.", 400

        # Get today's date from the database
        cursor.execute("SELECT CURRENT_DATE")
        today = cursor.fetchone()[0]

        # Calculate overdue days
        if return_date:
            end_date = return_date
        else:
            end_date = today

        overdue_days = max((end_date - due_date).days, 0)

        # Fine is Rs. 10 per overdue day
        fine_amount = overdue_days * 10

        # Prevent duplicate account records
        cursor.execute("""
            SELECT account_id
            FROM account
            WHERE borrowing_id = %s
        """, (borrowing_id,))

        existing_account = cursor.fetchone()

        if existing_account:
            cursor.close()
            return (
                "An account record already exists for this borrowing. "
                "No duplicate record was added."
            ), 400

        # Save the calculated fine
        cursor.execute("""
            INSERT INTO account
                (member_id, borrowing_id, amount, transaction_date, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            member_id,
            borrowing_id,
            fine_amount,
            today,
            "Unpaid"
        ))

        connection.commit()
        cursor.close()

        return redirect("/member-accounts")

    # Get members for the dropdown
    cursor.execute("""
        SELECT member_id, member_name
        FROM member
        ORDER BY member_name
    """)
    members = cursor.fetchall()

    # Get borrowing details for the dropdown and fine preview
    cursor.execute("""
        SELECT
            br.borrowing_id,
            b.title,
            m.member_name,
            br.due_date,
            br.return_date,
            br.member_id
        FROM borrowing br
        JOIN book_copy bc ON br.copy_id = bc.copy_id
        JOIN book b ON bc.book_id = b.book_id
        JOIN member m ON br.member_id = m.member_id
        ORDER BY br.borrowing_id
    """)
    borrowings = cursor.fetchall()

    cursor.close()

    return render_template(
        "add_account.html",
        members=members,
        borrowings=borrowings
    )


@app.route("/edit-account/<int:account_id>", methods=["GET", "POST"])
def edit_account(account_id):
    cursor = connection.cursor()

    if request.method == "POST":
        member_id = request.form["member_id"]
        borrowing_id = request.form["borrowing_id"]
        amount = request.form["amount"]
        transaction_date = request.form["transaction_date"]
        status = request.form["status"]

        cursor.execute("""
            UPDATE account
            SET member_id = %s,
                borrowing_id = %s,
                amount = %s,
                transaction_date = %s,
                status = %s
            WHERE account_id = %s
        """, (
            member_id,
            borrowing_id,
            amount,
            transaction_date,
            status,
            account_id
        ))

        connection.commit()
        cursor.close()

        return redirect("/member-accounts")

    cursor.execute("""
        SELECT account_id,
               member_id,
               borrowing_id,
               amount,
               transaction_date,
               status
        FROM account
        WHERE account_id = %s
    """, (account_id,))

    account_record = cursor.fetchone()

    cursor.execute("""
        SELECT member_id, member_name
        FROM member
        ORDER BY member_name
    """)
    members = cursor.fetchall()

    cursor.execute("""
        SELECT
            br.borrowing_id,
            b.title,
            m.member_name
        FROM borrowing br
        JOIN book_copy bc
            ON br.copy_id = bc.copy_id
        JOIN book b
            ON bc.book_id = b.book_id
        JOIN member m
            ON br.member_id = m.member_id
        ORDER BY br.borrowing_id
    """)
    borrowings = cursor.fetchall()

    cursor.close()

    return render_template(
        "edit_account.html",
        account=account_record,
        members=members,
        borrowings=borrowings
    )

@app.route("/delete-account/<int:account_id>", methods=["POST"])
def delete_account(account_id):
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM account
        WHERE account_id = %s
    """, (account_id,))

    connection.commit()
    cursor.close()

    return redirect("/member-accounts")

if __name__ == "__main__":
    app.run()                                #debug=True
