from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='admin')  # superadmin, admin, pharmacist, cashier
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='users')
    
    def __repr__(self):
        return f'<User {self.email}>'

class Pharmacy(db.Model):
    __tablename__ = 'pharmacies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text)
    logo_url = db.Column(db.String(255))
    mpesa_till = db.Column(db.String(20), default='123456')
    receipt_footer = db.Column(db.Text, default='Thank you for your business!')
    is_active = db.Column(db.Boolean, default=True)
    terms_accepted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Pharmacy {self.name}>'

class License(db.Model):
    __tablename__ = 'licenses'
    
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, active, expired
    amount = db.Column(db.Float, default=3000.0)
    start_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='licenses')
    
    def is_expired(self):
        return self.expiry_date and datetime.utcnow() > self.expiry_date
    
    def __repr__(self):
        return f'<License {self.pharmacy_id} - {self.status}>'

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    license_id = db.Column(db.Integer, db.ForeignKey('licenses.id'), nullable=True)
    mpesa_code = db.Column(db.String(20), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, rejected
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    confirmation_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='payments')
    license = db.relationship('License', backref='payments')
    confirmer = db.relationship('User', backref='confirmed_payments')
    
    def __repr__(self):
        return f'<Payment {self.mpesa_code}>'

class Drug(db.Model):
    __tablename__ = 'drugs'
    
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    batch_number = db.Column(db.String(50))
    barcode = db.Column(db.String(50))
    expiry_date = db.Column(db.Date)
    quantity = db.Column(db.Integer, default=0)
    purchase_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    reorder_level = db.Column(db.Integer, default=10)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='drugs')
    
    def is_low_stock(self):
        return self.quantity <= self.reorder_level
    
    def is_expired(self):
        return self.expiry_date and datetime.utcnow().date() > self.expiry_date
    
    def is_expiring_soon(self, days=30):
        if not self.expiry_date:
            return False
        return (self.expiry_date - datetime.utcnow().date()).days <= days
    
    def __repr__(self):
        return f'<Drug {self.name}>'

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    id_number = db.Column(db.String(20))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='customers')
    
    def __repr__(self):
        return f'<Customer {self.name}>'

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receipt_number = db.Column(db.String(20), unique=True, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, mpesa
    mpesa_reference = db.Column(db.String(50))
    prescription_number = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='sales')
    customer = db.relationship('Customer', backref='purchases')
    cashier = db.relationship('User', backref='sales_made')
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Sale {self.receipt_number}>'

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey('drugs.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    # Relationships
    drug = db.relationship('Drug', backref='sale_items')
    
    def __repr__(self):
        return f'<SaleItem {self.drug.name} x {self.quantity}>'

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    receipt_number = db.Column(db.String(50))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='expenses')
    creator = db.relationship('User', backref='expenses_created')
    
    def __repr__(self):
        return f'<Expense {self.description}>'
