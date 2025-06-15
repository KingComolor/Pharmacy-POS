from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from auth import license_required, same_pharmacy_required, role_required
from models import Drug
from app import db
from datetime import datetime

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def index():
    """Inventory listing"""
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    
    query = Drug.query.filter_by(pharmacy_id=current_user.pharmacy_id)
    
    if search:
        query = query.filter(
            Drug.name.ilike(f'%{search}%') |
            Drug.barcode.ilike(f'%{search}%')
        )
    
    if category:
        query = query.filter_by(category=category)
    
    drugs = query.order_by(Drug.name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get categories for filter
    categories = db.session.query(Drug.category).filter_by(
        pharmacy_id=current_user.pharmacy_id
    ).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('inventory/index.html',
                         drugs=drugs,
                         categories=categories,
                         search=search,
                         selected_category=category)

@inventory_bp.route('/add', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def add_drug():
    """Add new drug"""
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        batch_number = request.form.get('batch_number')
        barcode = request.form.get('barcode')
        expiry_date = request.form.get('expiry_date')
        quantity = request.form.get('quantity', type=int)
        purchase_price = request.form.get('purchase_price', type=float)
        selling_price = request.form.get('selling_price', type=float)
        reorder_level = request.form.get('reorder_level', type=int)
        description = request.form.get('description')
        
        # Validation
        errors = []
        if not name:
            errors.append('Drug name is required.')
        if not purchase_price or purchase_price <= 0:
            errors.append('Valid purchase price is required.')
        if not selling_price or selling_price <= 0:
            errors.append('Valid selling price is required.')
        if quantity is None or quantity < 0:
            errors.append('Valid quantity is required.')
        
        # Check for duplicate barcode
        if barcode:
            existing = Drug.query.filter_by(
                pharmacy_id=current_user.pharmacy_id,
                barcode=barcode
            ).first()
            if existing:
                errors.append('A drug with this barcode already exists.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('inventory/add_drug.html')
        
        try:
            # Parse expiry date
            expiry_date_obj = None
            if expiry_date:
                expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            
            drug = Drug(
                pharmacy_id=current_user.pharmacy_id,
                name=name,
                category=category,
                batch_number=batch_number,
                barcode=barcode,
                expiry_date=expiry_date_obj,
                quantity=quantity or 0,
                purchase_price=purchase_price,
                selling_price=selling_price,
                reorder_level=reorder_level or 10,
                description=description
            )
            db.session.add(drug)
            db.session.commit()
            
            flash('Drug added successfully!', 'success')
            return redirect(url_for('inventory.index'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to add drug. Please try again.', 'error')
    
    return render_template('inventory/add_drug.html')

@inventory_bp.route('/edit/<int:drug_id>', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def edit_drug(drug_id):
    """Edit drug"""
    drug = Drug.query.filter_by(
        id=drug_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        batch_number = request.form.get('batch_number')
        barcode = request.form.get('barcode')
        expiry_date = request.form.get('expiry_date')
        quantity = request.form.get('quantity', type=int)
        purchase_price = request.form.get('purchase_price', type=float)
        selling_price = request.form.get('selling_price', type=float)
        reorder_level = request.form.get('reorder_level', type=int)
        description = request.form.get('description')
        
        # Validation
        errors = []
        if not name:
            errors.append('Drug name is required.')
        if not purchase_price or purchase_price <= 0:
            errors.append('Valid purchase price is required.')
        if not selling_price or selling_price <= 0:
            errors.append('Valid selling price is required.')
        if quantity is None or quantity < 0:
            errors.append('Valid quantity is required.')
        
        # Check for duplicate barcode (excluding current drug)
        if barcode:
            existing = Drug.query.filter_by(
                pharmacy_id=current_user.pharmacy_id,
                barcode=barcode
            ).filter(Drug.id != drug_id).first()
            if existing:
                errors.append('A drug with this barcode already exists.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('inventory/edit_drug.html', drug=drug)
        
        try:
            # Parse expiry date
            expiry_date_obj = None
            if expiry_date:
                expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            
            # Update drug
            drug.name = name
            drug.category = category
            drug.batch_number = batch_number
            drug.barcode = barcode
            drug.expiry_date = expiry_date_obj
            drug.quantity = quantity or 0
            drug.purchase_price = purchase_price
            drug.selling_price = selling_price
            drug.reorder_level = reorder_level or 10
            drug.description = description
            
            db.session.commit()
            
            flash('Drug updated successfully!', 'success')
            return redirect(url_for('inventory.index'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to update drug. Please try again.', 'error')
    
    return render_template('inventory/edit_drug.html', drug=drug)

@inventory_bp.route('/delete/<int:drug_id>', methods=['POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def delete_drug(drug_id):
    """Delete drug"""
    drug = Drug.query.filter_by(
        id=drug_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    try:
        db.session.delete(drug)
        db.session.commit()
        flash('Drug deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete drug. Please try again.', 'error')
    
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/search')
@login_required
@license_required
@same_pharmacy_required
def search_drugs():
    """AJAX search for drugs"""
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify([])
    
    drugs = Drug.query.filter_by(pharmacy_id=current_user.pharmacy_id).filter(
        Drug.name.ilike(f'%{query}%') |
        Drug.barcode.ilike(f'%{query}%')
    ).filter(Drug.quantity > 0).limit(10).all()
    
    results = []
    for drug in drugs:
        results.append({
            'id': drug.id,
            'name': drug.name,
            'price': drug.selling_price,
            'quantity': drug.quantity,
            'barcode': drug.barcode
        })
    
    return jsonify(results)
