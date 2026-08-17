import os
import sqlite3
import uuid
import webbrowser
from datetime import datetime
from functools import wraps
from threading import Timer

from flask import Flask, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "gadzivo.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config.update(SECRET_KEY="change-this-secret-key-before-production", UPLOAD_FOLDER=UPLOAD_FOLDER,
                  MAX_CONTENT_LENGTH=15 * 1024 * 1024)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id") or not session.get("is_admin"):
            flash("Administrator access is required.", "danger")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        raise ValueError("Please upload a PNG, JPG, JPEG, GIF, or WEBP image.")
    extension = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{extension}"
    file.save(os.path.join(UPLOAD_FOLDER, name))
    return name


def save_images(files):
    """Validate and save a selection of product photos, skipping empty inputs."""
    return [saved for saved in (save_image(file) for file in files) if saved]


def init_db():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT NOT NULL,
        price REAL NOT NULL, discount_price REAL, stock INTEGER NOT NULL DEFAULT 0,
        image TEXT, category_id INTEGER, created_at TEXT NOT NULL,
        FOREIGN KEY(category_id) REFERENCES categories(id)
    );
    CREATE TABLE IF NOT EXISTS product_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, image TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS carts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1, UNIQUE(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, customer_name TEXT NOT NULL,
        phone TEXT NOT NULL, email TEXT NOT NULL, address TEXT NOT NULL, city TEXT NOT NULL,
        total REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Pending', created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, product_id INTEGER,
        product_name TEXT NOT NULL, price REAL NOT NULL, quantity INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    """)
    if not query("SELECT id FROM users WHERE email = ?", ("admin@gadzivo.com",), one=True):
        db.execute("INSERT INTO users (name,email,password,is_admin,created_at) VALUES (?,?,?,?,?)",
                   ("Gadzivo Admin", "admin@gadzivo.com", generate_password_hash("admin123"), 1, datetime.now().isoformat()))
    if not query("SELECT id FROM categories", one=True):
        for name in ("Electronics", "Fashion", "Home & Living", "Beauty", "Groceries", "Sports & Outdoors", "Baby & Toys", "Health & Care"):
            db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        samples = [
            ("Wireless Headphones", "Comfortable over-ear headphones with rich sound and long battery life.", 2490, 1990, 12, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80", 1),
            ("Smart Watch", "Track calls, workouts and daily activity from your wrist.", 3290, 2890, 8, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=800&q=80", 1),
            ("Classic Backpack", "A durable everyday backpack with room for all your essentials.", 1590, None, 15, "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80", 2),
            ("Minimal Table Lamp", "Warm, modern lighting for a welcoming home.", 1890, 1590, 6, "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=800&q=80", 3),
            ("Portable Bluetooth Speaker", "Water-resistant speaker for music at home and outside.", 1890, 1490, 20, "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=800&q=80", 1),
            ("Everyday Sneakers", "Lightweight sneakers designed for everyday comfort.", 2690, 2090, 10, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=80", 2),
            ("Skin Care Set", "A simple three-step routine for a fresh daily glow.", 1290, 990, 18, "https://images.unsplash.com/photo-1556228578-8c89e6adf883?auto=format&fit=crop&w=800&q=80", 4),
            ("Stainless Water Bottle", "Insulated bottle that keeps drinks cold through the day.", 890, None, 30, "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=800&q=80", 3),
        ]
        db.executemany("INSERT INTO products (name,description,price,discount_price,stock,image,category_id,created_at) VALUES (?,?,?,?,?,?,?,?)",
                       [item + (datetime.now().isoformat(),) for item in samples])
    db.commit()


@app.context_processor
def inject_globals():
    count = 0
    if session.get("user_id"):
        row = query("SELECT COALESCE(SUM(quantity),0) AS count FROM carts WHERE user_id=?", (session["user_id"],), one=True)
        count = row["count"]
    return {"cart_count": count}


@app.route("/")
def index():
    products = query("SELECT p.*, c.name AS category FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC LIMIT 12")
    deals = query("SELECT p.*, c.name AS category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.discount_price IS NOT NULL AND p.stock > 0 ORDER BY (p.price - p.discount_price) DESC LIMIT 6")
    categories = query("SELECT c.*, COUNT(p.id) AS product_count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id")
    return render_template("index.html", products=products, deals=deals, categories=categories)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/products")
def products():
    term = request.args.get("q", "").strip()
    category = request.args.get("category", type=int)
    sort = request.args.get("sort", "newest")
    order = {"price_low": "COALESCE(p.discount_price,p.price) ASC", "price_high": "COALESCE(p.discount_price,p.price) DESC"}.get(sort, "p.id DESC")
    where, args = [], []
    if term:
        where.append("(p.name LIKE ? OR p.description LIKE ?)"); args.extend([f"%{term}%", f"%{term}%"])
    if category:
        where.append("p.category_id=?"); args.append(category)
    clause = " WHERE " + " AND ".join(where) if where else ""
    items = query(f"SELECT p.*,c.name AS category FROM products p LEFT JOIN categories c ON c.id=p.category_id{clause} ORDER BY {order}", args)
    return render_template("products.html", products=items, categories=query("SELECT * FROM categories ORDER BY name"), term=term, selected_category=category, sort=sort)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = query("SELECT p.*,c.name AS category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=?", (product_id,), True)
    if not product: return ("Product not found", 404)
    images = query("SELECT * FROM product_images WHERE product_id=? ORDER BY position,id", (product_id,))
    return render_template("product_detail.html", product=product, images=images)


@app.post("/cart/add/<int:product_id>")
@login_required
def add_to_cart(product_id):
    product = query("SELECT * FROM products WHERE id=?", (product_id,), True)
    quantity = max(1, request.form.get("quantity", 1, type=int))
    if not product or product["stock"] < 1:
        flash("This product is currently unavailable.", "danger"); return redirect(request.referrer or url_for("products"))
    existing = query("SELECT * FROM carts WHERE user_id=? AND product_id=?", (session["user_id"], product_id), True)
    if existing:
        new_qty = min(existing["quantity"] + quantity, product["stock"])
        get_db().execute("UPDATE carts SET quantity=? WHERE id=?", (new_qty, existing["id"]))
    else:
        get_db().execute("INSERT INTO carts (user_id,product_id,quantity) VALUES (?,?,?)", (session["user_id"], product_id, min(quantity, product["stock"])))
    get_db().commit(); flash("Added to your cart.", "success")
    return redirect(request.referrer or url_for("cart"))


@app.post("/buy-now/<int:product_id>")
@login_required
def buy_now(product_id):
    product = query("SELECT * FROM products WHERE id=?", (product_id,), True)
    quantity = max(1, request.form.get("quantity", 1, type=int))
    if not product or product["stock"] < 1:
        flash("This product is currently unavailable.", "danger")
        return redirect(url_for("products"))
    existing = query("SELECT * FROM carts WHERE user_id=? AND product_id=?", (session["user_id"], product_id), True)
    if existing:
        get_db().execute("UPDATE carts SET quantity=? WHERE id=?", (min(existing["quantity"] + quantity, product["stock"]), existing["id"]))
    else:
        get_db().execute("INSERT INTO carts (user_id,product_id,quantity) VALUES (?,?,?)", (session["user_id"], product_id, min(quantity, product["stock"])))
    get_db().commit()
    return redirect(url_for("checkout"))


def cart_items():
    return query("SELECT carts.id AS cart_id,carts.quantity,p.* FROM carts JOIN products p ON p.id=carts.product_id WHERE carts.user_id=?", (session["user_id"],))


@app.route("/cart")
@login_required
def cart():
    items = cart_items(); total = sum((item["discount_price"] or item["price"]) * item["quantity"] for item in items)
    return render_template("cart.html", items=items, total=total)


@app.post("/cart/update/<int:cart_id>")
@login_required
def update_cart(cart_id):
    item = query("SELECT carts.*,p.stock FROM carts JOIN products p ON p.id=carts.product_id WHERE carts.id=? AND carts.user_id=?", (cart_id,session["user_id"]), True)
    if item:
        quantity = request.form.get("quantity", 1, type=int)
        if quantity <= 0: get_db().execute("DELETE FROM carts WHERE id=?", (cart_id,))
        else: get_db().execute("UPDATE carts SET quantity=? WHERE id=?", (min(quantity,item["stock"]),cart_id))
        get_db().commit()
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:cart_id>")
@login_required
def remove_cart(cart_id):
    get_db().execute("DELETE FROM carts WHERE id=? AND user_id=?", (cart_id,session["user_id"])); get_db().commit()
    flash("Item removed from cart.", "info"); return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = cart_items(); total = sum((i["discount_price"] or i["price"]) * i["quantity"] for i in items)
    if not items:
        flash("Your cart is empty.", "warning"); return redirect(url_for("products"))
    user = query("SELECT * FROM users WHERE id=?", (session["user_id"],), True)
    if request.method == "POST":
        fields = [request.form.get(k," ").strip() for k in ("customer_name","phone","email","address","city")]
        if not all(fields): flash("Please complete every delivery field.", "danger")
        else:
            db = get_db(); cur = db.execute("INSERT INTO orders (user_id,customer_name,phone,email,address,city,total,created_at) VALUES (?,?,?,?,?,?,?,?)", (session["user_id"],*fields,total,datetime.now().isoformat()))
            order_id = cur.lastrowid
            for item in items:
                price = item["discount_price"] or item["price"]
                db.execute("INSERT INTO order_items (order_id,product_id,product_name,price,quantity) VALUES (?,?,?,?,?)", (order_id,item["id"],item["name"],price,item["quantity"]))
                db.execute("UPDATE products SET stock=MAX(0,stock-?) WHERE id=?", (item["quantity"],item["id"]))
            db.execute("DELETE FROM carts WHERE user_id=?", (session["user_id"],)); db.commit()
            flash("Your Cash on Delivery order was placed successfully!", "success"); return redirect(url_for("my_orders"))
    return render_template("checkout.html", items=items,total=total,user=user)


@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name,email,password = (request.form.get(k,"").strip() for k in ("name","email","password"))
        if len(name)<2 or "@" not in email or len(password)<6: flash("Use a valid name/email and a password of at least 6 characters.", "danger")
        elif query("SELECT id FROM users WHERE email=?", (email.lower(),), True): flash("That email is already registered.", "danger")
        else:
            db=get_db(); db.execute("INSERT INTO users (name,email,password,created_at) VALUES (?,?,?,?)",(name,email.lower(),generate_password_hash(password),datetime.now().isoformat())); db.commit()
            flash("Account created. Please log in.", "success"); return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user=query("SELECT * FROM users WHERE email=?", (request.form.get("email","").strip().lower(),), True)
        if user and check_password_hash(user["password"],request.form.get("password", "")):
            session.clear(); session.update(user_id=user["id"],user_name=user["name"],is_admin=bool(user["is_admin"]))
            flash("Welcome back!", "success"); return redirect(request.args.get("next") or (url_for("admin_dashboard") if user["is_admin"] else url_for("index")))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout(): session.clear(); flash("You have been logged out.", "info"); return redirect(url_for("index"))


@app.route("/profile")
@login_required
def profile(): return render_template("profile.html", user=query("SELECT * FROM users WHERE id=?",(session["user_id"],),True))


@app.route("/orders")
@login_required
def my_orders(): return render_template("orders.html", orders=query("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(session["user_id"],)))


@app.route("/admin")
@admin_required
def admin_dashboard():
    stats={"products":query("SELECT COUNT(*) AS n FROM products",one=True)["n"],"customers":query("SELECT COUNT(*) AS n FROM users WHERE is_admin=0",one=True)["n"],"orders":query("SELECT COUNT(*) AS n FROM orders WHERE status='Pending'",one=True)["n"],"sales":query("SELECT COALESCE(SUM(total),0) AS n FROM orders WHERE status!='Cancelled'",one=True)["n"]}
    return render_template("admin/dashboard.html",stats=stats,orders=query("SELECT * FROM orders ORDER BY id DESC LIMIT 8"))


@app.route("/admin/products", methods=["GET","POST"])
@admin_required
def admin_products():
    if request.method=="POST":
        try:
            images = save_images(request.files.getlist("images"))
            image_url = request.form.get("image_url", "").strip()
            primary = images[0] if images else image_url or None
            db = get_db()
            cursor = db.execute("INSERT INTO products (name,description,price,discount_price,stock,image,category_id,created_at) VALUES (?,?,?,?,?,?,?,?)",(request.form["name"].strip(),request.form["description"].strip(),float(request.form["price"]),float(request.form["discount_price"]) if request.form.get("discount_price") else None,int(request.form["stock"]),primary,request.form.get("category_id",type=int),datetime.now().isoformat()))
            for position, image in enumerate(images):
                db.execute("INSERT INTO product_images (product_id,image,position) VALUES (?,?,?)", (cursor.lastrowid, image, position))
            db.commit(); flash("Product and photos added.","success")
        except (ValueError,KeyError): flash("Please check the product details and image type.","danger")
        return redirect(url_for("admin_products"))
    return render_template("admin/products.html",products=query("SELECT p.*,c.name AS category FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC"),categories=query("SELECT * FROM categories ORDER BY name"))


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_product(product_id):
    product = query("SELECT * FROM products WHERE id=?", (product_id,), True)
    if not product:
        return ("Product not found", 404)
    if request.method == "POST":
        try:
            images = save_images(request.files.getlist("images"))
            image_url = request.form.get("image_url", "").strip()
            primary = images[0] if images else (image_url or product["image"])
            db = get_db()
            db.execute("UPDATE products SET name=?,description=?,price=?,discount_price=?,stock=?,image=?,category_id=? WHERE id=?", (request.form["name"].strip(), request.form["description"].strip(), float(request.form["price"]), float(request.form["discount_price"]) if request.form.get("discount_price") else None, int(request.form["stock"]), primary, request.form.get("category_id", type=int), product_id))
            start = query("SELECT COALESCE(MAX(position), -1) AS n FROM product_images WHERE product_id=?", (product_id,), True)["n"] + 1
            for position, image in enumerate(images, start=start):
                db.execute("INSERT INTO product_images (product_id,image,position) VALUES (?,?,?)", (product_id, image, position))
            db.commit(); flash("Product updated.", "success")
            return redirect(url_for("admin_products"))
        except (ValueError, KeyError):
            flash("Please check the product details and image type.", "danger")
    return render_template("admin/edit_product.html", product=product, categories=query("SELECT * FROM categories ORDER BY name"), images=query("SELECT * FROM product_images WHERE product_id=? ORDER BY position,id", (product_id,)))


@app.post("/admin/products/<int:product_id>/delete")
@admin_required
def admin_delete_product(product_id):
    db = get_db(); db.execute("DELETE FROM product_images WHERE product_id=?", (product_id,)); db.execute("DELETE FROM products WHERE id=?",(product_id,)); db.commit(); flash("Product deleted.","info"); return redirect(url_for("admin_products"))


@app.route("/admin/orders")
@admin_required
def admin_orders(): return render_template("admin/orders.html",orders=query("SELECT * FROM orders ORDER BY id DESC"))


@app.post("/admin/orders/<int:order_id>/status")
@admin_required
def admin_order_status(order_id):
    status=request.form.get("status");
    if status in ("Pending","Confirmed","Shipped","Delivered","Cancelled"): get_db().execute("UPDATE orders SET status=? WHERE id=?",(status,order_id));get_db().commit();flash("Order status updated.","success")
    return redirect(url_for("admin_orders"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    Timer(1, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=True, use_reloader=False)
