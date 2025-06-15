from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from auth import license_required, same_pharmacy_required, role_required
from models import Expense
from app import db
from datetime import datetime

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def index():
    """Expenses listing"""
    category = request.args.get('category', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    page = request.args.get('page', 1, type=int)
    
    query = Expense.query.filter_by(pharmacy_id=current_user.pharmacy_id)
    
    if category:
        query = query.filter_by(category=category)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Expense.date >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Expense.date <= date_to_obj)
        except ValueError:
            pass
    
    expenses = query.order_by(Expense.date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get categories for filter
    categories = db.session.query(Expense.category).filter_by(
        pharmacy_id=current_user.pharmacy_id
    ).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    # Calculate total for current filters
    total_amount = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.pharmacy_id == current_user.pharmacy_id
    )
    
    if category:
        total_amount = total_amount.filter_by(category=category)
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            total_amount = total_amount.filter(Expense.date >= date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            total_amount = total_amount.filter(Expense.date <= date_to_obj)
        except ValueError:
            pass
    
    total_amount = total_amount.scalar() or 0
    
    return render_template('expenses/index.html',
                         expenses=expenses,
                         categories=categories,
                         selected_category=category,
                         date_from=date_from,
                         date_to=date_to,
                         total_amount=total_amount)

@expenses_bp.route('/add', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def add_expense():
    """Add new expense"""
    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description')
        amount = request.form.get('amount', type=float)
        date = request.form.get('date')
        receipt_number = request.form.get('receipt_number')
        
        # Validation
        errors = []
        if not category:
            errors.append('Category is required.')
        if not description:
            errors.append('Description is required.')
        if not amount or amount <= 0:
            errors.append('Valid amount is required.')
        if not date:
            errors.append('Date is required.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('expenses/add_expense.html')
        
        try:
            # Parse date
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            
            expense = Expense(
                pharmacy_id=current_user.pharmacy_id,
                category=category,
                description=description,
                amount=amount,
                date=date_obj,
                receipt_number=receipt_number,
                created_by=current_user.id
            )
            db.session.add(expense)
            db.session.commit()
            
            flash('Expense added successfully!', 'success')
            return redirect(url_for('expenses.index'))
            
        except ValueError:
            flash('Invalid date format.', 'error')
        except Exception as e:
            db.session.rollback()
            flash('Failed to add expense. Please try again.', 'error')
    
    # Common expense categories
    common_categories = [
        'Rent', 'Utilities', 'Staff Salaries', 'Insurance', 'Marketing',
        'Office Supplies', 'Equipment', 'Maintenance', 'Transport', 'Other'
    ]
    
    return render_template('expenses/add_expense.html',
                         common_categories=common_categories)

@expenses_bp.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def edit_expense(expense_id):
    """Edit expense"""
    expense = Expense.query.filter_by(
        id=expense_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description')
        amount = request.form.get('amount', type=float)
        date = request.form.get('date')
        receipt_number = request.form.get('receipt_number')
        
        # Validation
        errors = []
        if not category:
            errors.append('Category is required.')
        if not description:
            errors.append('Description is required.')
        if not amount or amount <= 0:
            errors.append('Valid amount is required.')
        if not date:
            errors.append('Date is required.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('expenses/add_expense.html', expense=expense)
        
        try:
            # Parse date
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            
            expense.category = category
            expense.description = description
            expense.amount = amount
            expense.date = date_obj
            expense.receipt_number = receipt_number
            
            db.session.commit()
            
            flash('Expense updated successfully!', 'success')
            return redirect(url_for('expenses.index'))
            
        except ValueError:
            flash('Invalid date format.', 'error')
        except Exception as e:
            db.session.rollback()
            flash('Failed to update expense. Please try again.', 'error')
    
    # Common expense categories
    common_categories = [
        'Rent', 'Utilities', 'Staff Salaries', 'Insurance', 'Marketing',
        'Office Supplies', 'Equipment', 'Maintenance', 'Transport', 'Other'
    ]
    
    return render_template('expenses/add_expense.html',
                         expense=expense,
                         common_categories=common_categories)

@expenses_bp.route('/delete/<int:expense_id>', methods=['POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def delete_expense(expense_id):
    """Delete expense"""
    expense = Expense.query.filter_by(
        id=expense_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete expense. Please try again.', 'error')
    
    return redirect(url_for('expenses.index'))
