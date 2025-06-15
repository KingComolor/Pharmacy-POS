from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from auth import license_required, same_pharmacy_required, role_required
from models import Drug, Sale, SaleItem, Customer
from app import db
import uuid
from datetime import datetime

sales_bp = Blueprint('sales', __name__)

@sales_bp.route('/')
@login_required
@license_required
@same_pharmacy_required
def index():
    """Sales history"""
    page = request.args.get('page', 1, type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Sale.query.filter_by(pharmacy_id=current_user.pharmacy_id)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Sale.created_at) >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Sale.created_at) <= date_to_obj)
        except ValueError:
            pass
    
    sales = query.order_by(Sale.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('sales/index.html', sales=sales,
                         date_from=date_from, date_to=date_to)

@sales_bp.route('/pos')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def pos():
    """Point of Sale system"""
    # Clear any existing cart
    session.pop('cart', None)
    
    # Get customers for dropdown
    customers = Customer.query.filter_by(pharmacy_id=current_user.pharmacy_id).all()
    
    return render_template('sales/pos.html', customers=customers)

@sales_bp.route('/add-to-cart', methods=['POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def add_to_cart():
    """Add item to cart"""
    drug_id = request.json.get('drug_id')
    quantity = request.json.get('quantity', 1)
    
    drug = Drug.query.filter_by(
        id=drug_id,
        pharmacy_id=current_user.pharmacy_id
    ).first()
    
    if not drug:
        return jsonify({'success': False, 'message': 'Drug not found'})
    
    if drug.quantity < quantity:
        return jsonify({'success': False, 'message': 'Insufficient stock'})
    
    # Initialize cart if not exists
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    drug_id_str = str(drug_id)
    
    if drug_id_str in cart:
        # Check total quantity doesn't exceed stock
        new_quantity = cart[drug_id_str]['quantity'] + quantity
        if new_quantity > drug.quantity:
            return jsonify({'success': False, 'message': 'Insufficient stock'})
        cart[drug_id_str]['quantity'] = new_quantity
        cart[drug_id_str]['total'] = new_quantity * drug.selling_price
    else:
        cart[drug_id_str] = {
            'name': drug.name,
            'price': drug.selling_price,
            'quantity': quantity,
            'total': quantity * drug.selling_price
        }
    
    session['cart'] = cart
    session.modified = True
    
    # Calculate cart totals
    cart_total = sum(item['total'] for item in cart.values())
    cart_count = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'success': True,
        'cart_total': cart_total,
        'cart_count': cart_count,
        'cart': cart
    })

@sales_bp.route('/remove-from-cart', methods=['POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def remove_from_cart():
    """Remove item from cart"""
    drug_id = request.json.get('drug_id')
    
    if 'cart' not in session:
        return jsonify({'success': False, 'message': 'Cart is empty'})
    
    cart = session['cart']
    drug_id_str = str(drug_id)
    
    if drug_id_str in cart:
        del cart[drug_id_str]
        session['cart'] = cart
        session.modified = True
    
    # Calculate cart totals
    cart_total = sum(item['total'] for item in cart.values())
    cart_count = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'success': True,
        'cart_total': cart_total,
        'cart_count': cart_count,
        'cart': cart
    })

@sales_bp.route('/update-cart', methods=['POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def update_cart():
    """Update cart item quantity"""
    drug_id = request.json.get('drug_id')
    quantity = request.json.get('quantity', 1)
    
    if quantity <= 0:
        return remove_from_cart()
    
    drug = Drug.query.filter_by(
        id=drug_id,
        pharmacy_id=current_user.pharmacy_id
    ).first()
    
    if not drug:
        return jsonify({'success': False, 'message': 'Drug not found'})
    
    if drug.quantity < quantity:
        return jsonify({'success': False, 'message': 'Insufficient stock'})
    
    if 'cart' not in session:
        return jsonify({'success': False, 'message': 'Cart is empty'})
    
    cart = session['cart']
    drug_id_str = str(drug_id)
    
    if drug_id_str in cart:
        cart[drug_id_str]['quantity'] = quantity
        cart[drug_id_str]['total'] = quantity * drug.selling_price
        session['cart'] = cart
        session.modified = True
    
    # Calculate cart totals
    cart_total = sum(item['total'] for item in cart.values())
    cart_count = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'success': True,
        'cart_total': cart_total,
        'cart_count': cart_count,
        'cart': cart
    })

@sales_bp.route('/checkout', methods=['POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def checkout():
    """Process checkout"""
    if 'cart' not in session or not session['cart']:
        flash('Cart is empty', 'error')
        return redirect(url_for('sales.pos'))
    
    customer_id = request.form.get('customer_id')
    payment_method = request.form.get('payment_method')
    mpesa_reference = request.form.get('mpesa_reference')
    prescription_number = request.form.get('prescription_number')
    notes = request.form.get('notes')
    
    if not payment_method:
        flash('Payment method is required', 'error')
        return redirect(url_for('sales.pos'))
    
    if payment_method == 'mpesa' and not mpesa_reference:
        flash('M-PESA reference is required for M-PESA payments', 'error')
        return redirect(url_for('sales.pos'))
    
    cart = session['cart']
    
    try:
        # Generate receipt number
        receipt_number = f"RCP{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # Calculate total
        total_amount = sum(item['total'] for item in cart.values())
        
        # Create sale
        sale = Sale(
            pharmacy_id=current_user.pharmacy_id,
            customer_id=int(customer_id) if customer_id else None,
            cashier_id=current_user.id,
            receipt_number=receipt_number,
            total_amount=total_amount,
            payment_method=payment_method,
            mpesa_reference=mpesa_reference,
            prescription_number=prescription_number,
            notes=notes
        )
        db.session.add(sale)
        db.session.flush()  # Get sale ID
        
        # Create sale items and update stock
        for drug_id_str, item in cart.items():
            drug_id = int(drug_id_str)
            drug = Drug.query.filter_by(
                id=drug_id,
                pharmacy_id=current_user.pharmacy_id
            ).first()
            
            if not drug or drug.quantity < item['quantity']:
                raise Exception(f"Insufficient stock for {item['name']}")
            
            # Create sale item
            sale_item = SaleItem(
                sale_id=sale.id,
                drug_id=drug_id,
                quantity=item['quantity'],
                unit_price=item['price'],
                total_price=item['total']
            )
            db.session.add(sale_item)
            
            # Update drug stock
            drug.quantity -= item['quantity']
        
        db.session.commit()
        
        # Clear cart
        session.pop('cart', None)
        
        flash('Sale completed successfully!', 'success')
        return redirect(url_for('sales.receipt', sale_id=sale.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Checkout failed: {str(e)}', 'error')
        return redirect(url_for('sales.pos'))

@sales_bp.route('/receipt/<int:sale_id>')
@login_required
@license_required
@same_pharmacy_required
def receipt(sale_id):
    """Display receipt"""
    sale = Sale.query.filter_by(
        id=sale_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    return render_template('sales/receipt.html', sale=sale)

@sales_bp.route('/get-cart')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist', 'cashier')
def get_cart():
    """Get current cart contents"""
    cart = session.get('cart', {})
    cart_total = sum(item['total'] for item in cart.values())
    cart_count = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'cart': cart,
        'cart_total': cart_total,
        'cart_count': cart_count
    })
