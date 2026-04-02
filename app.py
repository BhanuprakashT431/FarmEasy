from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from datetime import datetime, timedelta
import random, os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func
from models import db, Order, User, Crop, Expense, Category, Transaction, B2BProduct, B2BOrder, CropTask
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join('static', 'profile_pics')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Init DB & Login
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_weather(city='Mandya'):
    try:
        response = requests.get('http://api.openweathermap.org/data/2.5/weather', params={
            'q': city,
            'appid': '642ff9553f263cb92624625684c74eb3',
            'units': 'metric'
        })
        data = response.json()
        if data.get('cod') != 200:
            return {'error': data.get('message', 'Failed to fetch weather')}
        return {
            'city': data['name'],
            'temperature': data['main']['temp'],
            'description': data['weather'][0]['description'],
            'icon': data['weather'][0]['icon']
        }
    except Exception as e:
        return {'error': str(e)}

# ========== ROUTES ==========

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

# ---------- Auth ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        if not all([email, password, confirm]):
            flash('Fill all fields.', 'danger')
        elif password != confirm:
            flash('Passwords do not match.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
        else:
            user = User(email=email, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash('Registered successfully.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            flash('Logged in!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for('login'))

# ---------- Dashboard ----------
@app.route('/dashboard')
@login_required
def dashboard():
    crops = Crop.query.filter_by(user_id=current_user.id).all()
    total_expenses = sum(sum(e.amount for e in crop.expenses) for crop in crops)
    total_transactions = db.session.query(func.count(Transaction.id)).join(Crop).filter(Crop.user_id == current_user.id).scalar()
    tips = [
        "Water early in the morning.",
        "Use crop rotation.",
        "Compost improves soil.",
        "Check weather forecasts.",
        "Mulch to retain moisture."
    ]
    
    # Financial Analytics (Group by Month for simple chart)
    chart_data = {'labels': [], 'expenses': [], 'income': []}
    transactions = db.session.query(Transaction).join(Crop).filter(Crop.user_id == current_user.id).order_by(Transaction.date).all()
    temp_data = {}
    for t in transactions:
        month = t.date.strftime("%Y-%m")
        if month not in temp_data:
            temp_data[month] = {'expense': 0, 'income': 0}
        temp_data[month][t.transaction_type] += t.amount
    
    for m in sorted(temp_data.keys()):
        chart_data['labels'].append(m)
        chart_data['expenses'].append(temp_data[m]['expense'])
        chart_data['income'].append(temp_data[m]['income'])

    return render_template('dashboard.html',
        user=current_user,
        profile_pic=current_user.profile_picture or 'default_profile.png',
        crops=crops,
        total_expenses=total_expenses,
        total_transactions=total_transactions,
        farming_tip=random.choice(tips),
        weather=get_weather(),
        chart_data=chart_data
    )

# ---------- Crop ----------
@app.route('/add_crop', methods=['GET', 'POST'])
@login_required
def add_crop():
    if request.method == 'POST':
        try:
            crop = Crop(
                user_id=current_user.id,
                name=request.form['name'],
                sowing_date=datetime.strptime(request.form['sowing_date'], '%Y-%m-%d').date(),
                harvest_date=datetime.strptime(request.form['harvest_date'], '%Y-%m-%d').date(),
                expected_yield=float(request.form['expected_yield']),
            )
            db.session.add(crop)
            db.session.commit()
            flash("Crop added!", "success")
            return redirect(url_for('dashboard'))
        except:
            flash("Invalid data.", "danger")
    return render_template('add_crop.html')

@app.route('/crop/<int:crop_id>')
def crop_detail(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    if crop.user_id != current_user.id:
        abort(403)

    # Fetch related transactions and expenses
    transactions = Transaction.query.filter_by(crop_id=crop.id).all()
    expenses = Expense.query.filter_by(crop_id=crop.id).all()

    return render_template(
        'crop_detail.html',
        crop=crop,
        transactions=transactions,
        expenses=expenses
    )

@app.route('/add_task/<int:crop_id>', methods=['POST'])
@login_required
def add_task(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    if crop.user_id != current_user.id:
        abort(403)
    try:
        task = CropTask(
            crop_id=crop_id,
            description=request.form['description'],
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date()
        )
        db.session.add(task)
        db.session.commit()
        flash("Task added!", "success")
    except Exception as e:
        flash("Failed to add task.", "danger")
    return redirect(url_for('crop_detail', crop_id=crop_id))

@app.route('/complete_task/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    task = CropTask.query.get_or_404(task_id)
    if task.crop.user_id != current_user.id:
        abort(403)
    task.is_completed = True
    db.session.commit()
    flash("Task completed!", "success")
    return redirect(url_for('crop_detail', crop_id=task.crop_id))

# ---------- Expense ----------
@app.route('/add_expense/<int:crop_id>', methods=['GET', 'POST'])
@login_required
def add_expense(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    if crop.user_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        try:
            expense = Expense(
                crop_id=crop_id,
                description=request.form['description'],
                amount=float(request.form['amount']),
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            )
            db.session.add(expense)
            db.session.commit()
            flash("Expense added!", "success")
            return redirect(url_for('crop_detail', crop_id=crop_id))
        except:
            flash("Invalid input.", "danger")
    return render_template('add_expense.html', crop=crop)

# ---------- Transaction ----------
@app.route('/add_transaction/<int:crop_id>', methods=['GET', 'POST'])
@login_required
def add_transaction(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    if crop.user_id != current_user.id:
        abort(403)
    categories = Category.query.all()
    if request.method == 'POST':
        try:
            transaction = Transaction(
                crop_id=crop_id,
                transaction_type=request.form['transaction_type'],
                amount=float(request.form['amount']),
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                notes=request.form['notes'],
                category_id=int(request.form['category'])
            )
            db.session.add(transaction)
            db.session.commit()
            flash("Transaction added!", "success")
            return redirect(url_for('crop_detail', crop_id=crop_id))
        except:
            flash("Invalid transaction data.", "danger")
    return render_template('add_transaction.html', crop=crop, categories=categories)

# ---------- Profile ----------
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.email = request.form.get('email')
        current_user.bio = request.form.get('bio')
        file = request.files.get('profile_pic')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.profile_picture = filename
        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for('dashboard'))
    return render_template('update_profile.html', user=current_user)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old = request.form.get('old_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')
        if not all([old, new, confirm]):
            flash("Fill all password fields.", "danger")
        elif new != confirm:
            flash("New passwords do not match.", "danger")
        elif not check_password_hash(current_user.password, old):
            flash("Incorrect old password.", "danger")
        else:
            current_user.password = generate_password_hash(new)
            db.session.commit()
            flash("Password changed.", "success")
            return redirect(url_for('profile'))
    return render_template('change_password.html')

# ---------- B2B ----------
@app.route('/buyers')
@login_required
def buyers_page():
    products = B2BProduct.query.filter_by(is_farm_product=True).all()
    return render_template('buyers.html', products=products)

@app.route("/b2b/products")
def b2b_products():
    return render_template("b2b_products.html", products=B2BProduct.query.all())

@app.route("/b2b/product/<int:product_id>")
def b2b_product_detail(product_id):
    return render_template("b2b_product_detail.html", product=B2BProduct.query.get_or_404(product_id))

@app.route("/place_b2b_order/<int:product_id>", methods=["POST"])
@login_required
def place_b2b_order(product_id):
    product = B2BProduct.query.get_or_404(product_id)
    try:
        quantity = int(request.form["quantity"])
        if quantity <= 0 or quantity > product.quantity:
            raise ValueError("Invalid quantity")
        product.quantity -= quantity
        order = B2BOrder(buyer_id=current_user.id, product_id=product_id, quantity=quantity, total_price=product.price * quantity)
        db.session.add(order)
        db.session.commit()
        flash("Order placed!", "success")
    except:
        flash("Failed to place order.", "danger")
    return redirect(url_for("buyers_page"))

@app.route("/b2b/my_orders")
@login_required
def my_b2b_orders():
    return render_template("my_b2b_orders.html", orders=B2BOrder.query.filter_by(buyer_id=current_user.id).all())

@app.route("/b2b/my_sales")
@login_required
def my_b2b_sales():
    return render_template("my_b2b_sales.html", products=B2BProduct.query.filter_by(seller_id=current_user.id).all())

# ---------- Order ----------
@app.route("/place-order/<int:product_id>", methods=["POST"])
@login_required
def place_order(product_id):
    product = B2BProduct.query.get_or_404(product_id)
    quantity = int(request.form['quantity'])
    address = request.form['delivery_address']
    total = product.price * quantity
    db.session.add(Order(user_id=current_user.id, product_id=product.id, quantity=quantity, delivery_address=address, total_price=total))
    db.session.commit()
    return redirect(url_for('my_orders'))

@app.route('/my-orders')
@login_required
def my_orders():
    return render_template('my_orders.html', orders=Order.query.filter_by(user_id=current_user.id).all())

@app.route("/update-address/<int:order_id>", methods=["POST"])
@login_required
def update_address(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    address = request.form.get("delivery_address")
    if not address:
        flash("Address cannot be empty", "danger")
    else:
        order.delivery_address = address
        order.expected_delivery = datetime.utcnow() + timedelta(days=3)
        db.session.commit()
        flash("Address updated.", "success")
    return redirect(url_for("my_orders"))

@app.route('/cancel-order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
    else:
        db.session.delete(order)
        db.session.commit()
        flash('Order cancelled.', 'success')
    return redirect(url_for('my_orders'))
@app.route("/add_b2b_product", methods=["GET", "POST"])
@login_required
def add_b2b_product():
    if request.method == "POST":
        try:
            title = request.form["title"]
            description = request.form["description"]
            price = float(request.form["price"])
            quantity = int(request.form["quantity"])
            is_farm_product = "is_farm_product" in request.form

            product = B2BProduct(
                seller_id=current_user.id,
                title=title,
                description=description,
                price=price,
                quantity=quantity,
                is_farm_product=is_farm_product
            )
            db.session.add(product)
            db.session.commit()
            flash("Product added!", "success")
            return redirect(url_for("b2b_products"))
        except Exception as e:
            flash(f"Error: {e}", "danger")

    return render_template("add_b2b_product.html")


# ---------- AI Chat ----------
@app.route('/api/chat', methods=['POST'])
@login_required
def ai_chat():
    user_msg = request.json.get('message', '').lower()
    responses = [
        "Based on current trends, ensure you irrigate early morning to prevent evaporation.",
        "Consider rotating your crops next season to maintain soil nitrogen levels.",
        "Always track your expenses closely using the dashboard to identify waste.",
        "Market prices for organic produce are rising—consider natural fertilizers."
    ]
    if "water" in user_msg or "irrigate" in user_msg:
        reply = "For optimal growth, water crops at the base early in the morning to reduce fungal diseases."
    elif "pest" in user_msg or "bug" in user_msg:
        reply = "Inspect leaves regularly. Neem oil is a great organic pesticide for early infestations."
    elif "fertilizer" in user_msg or "soil" in user_msg:
        reply = "Test your soil pH regularly. Adding compost can naturally improve nutrient retention."
    else:
        reply = random.choice(responses)
    return jsonify({"reply": reply})

# ---------- Run ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Category.query.first():
            db.session.add_all([
                Category(name='Seeds', type='expense'),
                Category(name='Fertilizers', type='expense'),
                Category(name='Labor', type='expense'),
                Category(name='Pesticides', type='expense'),
                Category(name='Machinery', type='expense'),
                Category(name='Irrigation', type='expense'),
                Category(name='Sales', type='income'),
                Category(name='Transport', type='expense'),
            ])
            db.session.commit()
            print("Default categories added.")
    app.run(debug=True)
