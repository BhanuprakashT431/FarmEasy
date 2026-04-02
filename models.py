from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    username = db.Column(db.String(100), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)

    crops = db.relationship('Crop', backref='user', lazy=True)
    b2b_products = db.relationship('B2BProduct', backref='seller', lazy=True)
    


class Crop(db.Model):
    __tablename__ = 'crop'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sowing_date = db.Column(db.String(20))
    expected_yield = db.Column(db.Float)
    harvest_date = db.Column(db.String(20))

    expenses = db.relationship('Expense', backref='crop', lazy=True)
    transactions = db.relationship('Transaction', backref='crop', lazy=True)


class Expense(db.Model):
    __tablename__ = 'expense'
    
    id = db.Column(db.Integer, primary_key=True)
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(20), nullable=False)


class Category(db.Model):
    __tablename__ = 'category'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    type = db.Column(db.String(10))  # 'income' or 'expense'

    transactions = db.relationship('Transaction', backref='category', lazy=True)


class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.String(200))
    transaction_type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'

    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)


# ========== B2B Models ==========
class B2BProduct(db.Model):
    __tablename__ = 'b2b_product'

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)  # ✅ Add this line
    is_farm_product = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('B2BOrder', backref='product', lazy=True)



    

class B2BOrder(db.Model):
    __tablename__ = 'b2b_order'

    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('b2b_product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    buyer = db.relationship('User', backref='b2b_orders')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
   

class Product(db.Model):
    __tablename__ = 'product'  # Explicitly define the table name

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('b2b_product.id'), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    delivery_address = db.Column(db.String(200), nullable=False)
    expected_delivery = db.Column(db.DateTime)

    product = db.relationship('B2BProduct')  # make sure this exists

