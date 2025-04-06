import psycopg2
from flask import Flask, g, request, jsonify
from config import host, user, password, db_name
from functools import wraps
import re
import secrets


app = Flask(__name__)
email_pattern = r"[^@]+@[a-zA-Z0-9.-]+\.[a-zA-Z0-9]+"
admin_key = "123456"


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(host=host, user=user, password=password, database = db_name)
        g.db.autocommit = True
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()



def with_cursor(func):
    @wraps(func)
    def wrapper (*args, **kwargs):
        with get_db().cursor() as cursor:
            return func(cursor, *args, **kwargs)
    return wrapper

@with_cursor
def check_customer(cursor, email = None, id = None):
    cursor.execute("select id, email from customers where id = %s or email = %s", (id, email))
    return cursor.fetchone()

    
@app.route("/online_shop/registration", methods = ["POST"])
@with_cursor
def registration (cursor):
    data = request.get_json(silent=True)
    if data is None or not data:
        return jsonify({"error":"No regitrsation info"}), 400
    user_email = data.get("email")
    valid_email = re.match(email_pattern, user_email)
    password = data.get("password")
    if valid_email is None or not user_email or not password:
        return jsonify({"error":"Введіть всі необхідні дані"}), 400
    try:
        if check_customer(email=user_email) is None:
            cursor.execute("insert into customers (email, password) values (%s,%s)", (user_email, password))
            return jsonify({"message":"Користувача успішно додано"}), 200
        else:
            return jsonify({"error" : "Користувач з таким email вже існує"}), 400
    except Exception as ex:
            return jsonify({"error" : str(ex)}), 500
    

    
@app.route("/online_shop/admin_registration", methods = ["POST"])
@with_cursor
def admin_registration (cursor):
    data = request.get_json(silent=True)
    if data is None or not data:
        return jsonify({"error":"No registration info"}), 400
    user_email = data.get("email")
    valid_email = re.match(email_pattern, user_email)
    password = data.get("password")
    check_key = data.get("admin_key")
    if valid_email is None or not user_email or not password or not check_key:
        return jsonify({"error":"Введіть всі необхідні дані"}), 400
    if check_key != admin_key:
        return jsonify({"error":"Invalid admin_key"}), 400
    try:
        if check_customer(email=user_email) is None:
            cursor.execute("insert into customers (email, password, role) values (%s,%s,'admin')", (user_email, password))
            return jsonify({"message":"Адміна успішно додано"}), 200
        else:
            return jsonify({"error" : "Адмін з таким email вже існує"}), 400
    except Exception as ex:
            return jsonify({"error" : str(ex)}), 500
    

@app.route("/online_shop/login", methods = ["POST"])
@with_cursor
def login(cursor):
    data = request.get_json(silent=True)
    if data is None or not data:
        return jsonify({"error":"No registration info"}), 400
    email = data.get("email")
    valid_email = re.match(email_pattern, email)
    password = data.get("password")
    if valid_email is None or not email or not password:
        return jsonify({"error":"Invalid email"}), 400
    cursor.execute("select email, password from customers where email = %s and password = %s", (email, password))
    user = cursor.fetchone()
    if user is None or not user:
        return jsonify({"error":"Невірний логін або пароль"}), 400
    session_id = secrets.token_hex(16)
    cursor.execute("update customers set session_id = %s where email = %s", (session_id, email))
    return jsonify({"message":"Успіх", "session_id":session_id}), 201


def login_required (func):
    @wraps(func)
    @with_cursor
    def wrapper(cursor, *args, **kwargs):
        try:
            session_id = request.headers.get("Authorization")
            if not session_id:
                return jsonify({"error":"Потрібна аутентифікація"}), 400
            session_id = session_id.replace("Session ", "")
            cursor.execute("select exists (select 1 from customers where session_id = %s)", (session_id,))
            if cursor.fetchone()[0]:
                return func(cursor,*args, **kwargs)
            return jsonify({"error":"Потрібна аутентифікація"}), 400
        except Exception as ex:
            return jsonify({"error": ex}), 400
    return wrapper


def admin_required (func):
    @wraps(func)
    @with_cursor
    def wrapper(cursor, *args, **kwargs):
        try:
            session_id = request.headers.get("Authorization")
            if not session_id:
                return jsonify({"error":"Потрібна аутентифікація"}), 400
            session_id = session_id.replace("Session ", "")
            cursor.execute("select role from customers where session_id = %s)", (session_id,))
            user = cursor.fetchone()[0]
            if user is None or not session_id:
                return jsonify({"error":"Потрібна аутентифікація"}), 400
            if user == "admin":
                return func(*args, **kwargs)
            return jsonify({"error":"Admin status required"}), 400
        except Exception as ex:
            return jsonify({"error": ex}), 400
    return wrapper


@app.route ("\online_shop\logout", methods = ["POST"])
@with_cursor
def logout (cursor):
    session_id = request.headers.get("Authorization")
    if not session_id:
        return jsonify({"error":"Потрібна аутентифікація"}), 400
    session_id = session_id.replace("Session ", "")
    cursor.execute("select exists (select 1 from customers where session_id = %s)", (session_id,))
    user = cursor.fetchone()[0]
    if user == True:
        cursor.execute("update customers set session_id = Null where session_id = %s", (session_id,))
        return jsonify({"message":"Logout successful"}), 201
    return jsonify({"error":"Logout failed"}), 400

@with_cursor
def check_product(cursor, id = None, name = None):
    cursor.execute("select id, name, price, quantity, access from products where id = %s or name = %s", (id, name))
    return cursor.fetchone()
    

    
@app.route("/online_shop/add_new_product", methods = ["POST"])
@admin_required
@with_cursor
def add_new_product(cursor):
    data = request.get_json(silent = True)
    if data is None:
        return jsonify({"error" : "No JSON provided or invalid format"}), 400
    product_name = data.get("name")
    price = data.get("price")
    quantity = data.get("quantity")
    description = data.get("description")
    access = data.get("access")
    if product_name is None or not isinstance(price, (int, float)) or not isinstance(quantity, (int, float)):
        return jsonify({"error": "All fields (name, price, quantity) must be provided and have correct types: name (string), price (number), quantity (number)"}), 400
    try:
        if quantity > 0 and price > 0 and check_product(name = product_name) is None:
            cursor.execute("""insert into products (name, description, price, quantity, access) values (%s, %s, %s, %s, %s)""", (product_name, description, price, quantity, access))
            return jsonify({"message" : "Товар додано!"}), 201
        else:
            return jsonify({"error" : "Неправльна кількість товару, невказана назва товару, неправильна ціна або товар вже існує!"}), 400
    except Exception as ex:
        return jsonify({"error" : str(ex)}), 500

@app.route("/online_shop/add_order", methods = ["POST"])
@login_required
@with_cursor
def add_order(cursor):
    data = request.get_json(silent = True)
    if data is None:
        return jsonify({"error" : "No JSON provided or invalid format"}), 400
    customer_id = data.get("customer_id")
    if customer_id is None:
        return jsonify({"error":"Customer ID required"}), 400
    order = data.get("order")
    if order is None or not order:
        return jsonify({"error":"Замовлення порожнє"}), 400
    try:
        products_ids = [int(key) for key in order.keys()]
        quantitys = [int(value) for value in order.values()]
    except ValueError:
        return jsonify({"error":"Invalid product id or product quantity"}), 400
    try:
        if check_customer(id = customer_id) is not None:
            cursor.execute("""insert into orders (customer_id) values (%s) returning id""", (customer_id, )) 
            order_id = cursor.fetchone()[0]
            errors = {}
            for product_id, quantity in zip (products_ids, quantitys):
                current_product = check_product(id = product_id)
                if current_product is not None and quantity > 0:
                    if current_product[3] == 0:
                        desc = "Товар закінчився!"
                        errors.update({current_product[1]: desc})
                    elif quantity <= current_product[3]:
                        cursor.execute("insert into order_details (order_id, product_id, quantity) values (%s, %s, %s)", (order_id, product_id, quantity))
                        new_quantity = current_product[3] - quantity
                        cursor.execute("update products set quantity = %s where id = %s", (new_quantity, product_id))
                        if new_quantity == 0:
                            cursor.execute("update products set access = FALSE where id = %s", (product_id,))
                    else:
                        cursor.execute("insert into order_details (order_id, product_id, quantity) values (%s, %s, %s)", (order_id, product_id, current_product[3]))
                        desc = f"Недостатня кількість товару на складі. В замовлення додано лише {current_product[3]} одиниці"
                        errors.update({current_product[1]: desc})
                        cursor.execute("update products set quantity = 0 where id = %s", (product_id,))
                        cursor.execute("update products set access = FALSE where id = %s", (product_id,))
            return jsonify({"message" : "Замовлення сформовано!", "errors" : errors}), 201  
        else:
            return jsonify({"error":"Цього користувача не існує!"}), 401
    except Exception as ex:
        return jsonify({"error" : str(ex)}), 500
            
@app.route("/online_shop/product_arrive", methods = ["POST"])
@admin_required
@with_cursor
def product_arrive(cursor):
    data = request.get_json(silent = True)
    if data is None:
        return jsonify({"error" : "No JSON provided or invalid format"}), 400
    arrive = data.get("arrive")
    if arrive is None or not arrive:
        return jsonify({"error":"Info not found"}), 400
    else:
        try:
            product_ids = [int(key) for key in arrive.keys()]
            quantitys = [int(value) for value in arrive.values()]
        except ValueError:
            return jsonify({"error":"Invalid product id or product quantity"}), 400
        errors = {}
        for product_id, quantity in zip(product_ids, quantitys):
            current_product = check_product(id = product_id)
            if quantity > 0 and current_product is not None:
                new_quantity = current_product[3] + quantity
                cursor.execute("update products set quantity = %s, access = TRUE where id = %s", (new_quantity, product_id))
            elif current_product is not None and quantity <= 0:
                desc = "Вказана неправильна кількість товару!"
                errors.update({current_product[1] : desc})
            elif current_product is None:
                desc = "Товару не існує!"
                errors.update({product_id: desc})
        return jsonify({"message":"Товари успішно оновлені!", "Не оновлені товари" : errors}),201
            
    
@app.route("/online_shop/all_products_info", methods = ["GET"])
@with_cursor
def all_products_info(cursor):
    cursor.execute("select name, price, access from products")
    products = [{"name" : row[0], "price" : float(row[1]), "access" : row[2]} for row in cursor.fetchall()]
    return jsonify(products), 200


@app.route("/online_shop/product_details/<int:product_id>", methods = ["GET"])
@with_cursor
def product_details(cursor, product_id):
    cursor.execute("select name, price, quantity, description, access from products where id = %s", (product_id,))
    info = cursor.fetchone()
    if info is not None:
        return jsonify({"name" : info[0], "price" : info[1], "quantity" : info[2], "description" : info[3], "access" : info[4]}), 200
    else:
        return jsonify({"error":"Product not found"}), 400

if __name__ == "__main__":
    app.run(debug=True)
