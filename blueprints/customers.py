from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from auth import license_required, same_pharmacy_required, role_required
from models import Customer, Sale
from app import db

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/')
@login_required
@license_required
@same_pharmacy_required
def index():
    """Customer listing"""
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    query = Customer.query.filter_by(pharmacy_id=current_user.pharmacy_id)
    
    if search:
        query = query.filter(
            Customer.name.ilike(f'%{search}%') |
            Customer.phone.ilike(f'%{search}%') |
            Customer.email.ilike(f'%{search}%')
        )
    
    customers = query.order_by(Customer.name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('customers/index.html',
                         customers=customers,
                         search=search)

@customers_bp.route('/add', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def add_customer():
    """Add new customer"""
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        id_number = request.form.get('id_number')
        address = request.form.get('address')
        
        # Validation
        if not name:
            flash('Customer name is required.', 'error')
            return render_template('customers/add_customer.html')
        
        # Check for duplicate phone or email
        existing = Customer.query.filter_by(pharmacy_id=current_user.pharmacy_id)
        if phone:
            if existing.filter_by(phone=phone).first():
                flash('A customer with this phone number already exists.', 'error')
                return render_template('customers/add_customer.html')
        
        if email:
            if existing.filter_by(email=email).first():
                flash('A customer with this email already exists.', 'error')
                return render_template('customers/add_customer.html')
        
        try:
            customer = Customer(
                pharmacy_id=current_user.pharmacy_id,
                name=name,
                phone=phone,
                email=email,
                id_number=id_number,
                address=address
            )
            db.session.add(customer)
            db.session.commit()
            
            flash('Customer added successfully!', 'success')
            return redirect(url_for('customers.index'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to add customer. Please try again.', 'error')
    
    return render_template('customers/add_customer.html')

@customers_bp.route('/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def edit_customer(customer_id):
    """Edit customer"""
    customer = Customer.query.filter_by(
        id=customer_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        id_number = request.form.get('id_number')
        address = request.form.get('address')
        
        # Validation
        if not name:
            flash('Customer name is required.', 'error')
            return render_template('customers/add_customer.html', customer=customer)
        
        # Check for duplicate phone or email (excluding current customer)
        existing = Customer.query.filter_by(pharmacy_id=current_user.pharmacy_id)
        if phone:
            if existing.filter_by(phone=phone).filter(Customer.id != customer_id).first():
                flash('A customer with this phone number already exists.', 'error')
                return render_template('customers/add_customer.html', customer=customer)
        
        if email:
            if existing.filter_by(email=email).filter(Customer.id != customer_id).first():
                flash('A customer with this email already exists.', 'error')
                return render_template('customers/add_customer.html', customer=customer)
        
        try:
            customer.name = name
            customer.phone = phone
            customer.email = email
            customer.id_number = id_number
            customer.address = address
            
            db.session.commit()
            
            flash('Customer updated successfully!', 'success')
            return redirect(url_for('customers.index'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to update customer. Please try again.', 'error')
    
    return render_template('customers/add_customer.html', customer=customer)

@customers_bp.route('/view/<int:customer_id>')
@login_required
@license_required
@same_pharmacy_required
def view_customer(customer_id):
    """View customer details and purchase history"""
    customer = Customer.query.filter_by(
        id=customer_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    # Get purchase history
    purchases = Sale.query.filter_by(
        customer_id=customer_id,
        pharmacy_id=current_user.pharmacy_id
    ).order_by(Sale.created_at.desc()).limit(20).all()
    
    # Calculate total spent
    total_spent = db.session.query(db.func.sum(Sale.total_amount)).filter_by(
        customer_id=customer_id,
        pharmacy_id=current_user.pharmacy_id
    ).scalar() or 0
    
    return render_template('customers/view_customer.html',
                         customer=customer,
                         purchases=purchases,
                         total_spent=total_spent)

@customers_bp.route('/delete/<int:customer_id>', methods=['POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def delete_customer(customer_id):
    """Delete customer"""
    customer = Customer.query.filter_by(
        id=customer_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    # Check if customer has purchases
    has_purchases = Sale.query.filter_by(customer_id=customer_id).first()
    if has_purchases:
        flash('Cannot delete customer with purchase history.', 'error')
        return redirect(url_for('customers.index'))
    
    try:
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete customer. Please try again.', 'error')
    
    return redirect(url_for('customers.index'))
