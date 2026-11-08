"""
╔══════════════════════════════════════════════════════════════════════╗
║   Aurora Finance Tracker — app.py                                    ║
║   Phase 4: Full Frontend & Backend Integration with CSV Engine       ║
║   Connects all UI pages, forms, and Chart.js to data/*.csv files     ║
╚══════════════════════════════════════════════════════════════════════╝

FEATURES IMPLEMENTED:
  - Real authentication against users.csv (SHA-256 hashed passwords)
  - Real session tracking with Flask sessions
  - Real transactions CRUD in transactions.csv
  - Real category budgets in budgets.csv with dynamic alert limits
  - Real savings milestones in savings_goals.csv
  - Audit logging of savings transfers in monthly_transfers.csv
  - Guaranteed financial calculations:
      Available Balance = Total Income − Total Expenses − Net Savings Contributions
  - Chart.js dynamic JSON feeds for all 8 charts
  - 100% persistent across server restarts
"""

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from functools import wraps
from datetime import date, datetime
from collections import defaultdict
import hashlib
import csv_storage

# ══════════════════════════════════════════════════════════════════════
# FLASK APPLICATION CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = "aurora_dark_finance_secure_session_key_2026_!@#"


# ══════════════════════════════════════════════════════════════════════
# AUTHENTICATION & HASHING HELPERS
# ══════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def check_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored SHA-256 hash."""
    return hash_password(plain_password) == hashed_password


def current_user() -> str:
    """Get active username from session."""
    return session.get("username", "")


def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            flash("Please sign in to access that page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ══════════════════════════════════════════════════════════════════════
# CORE FINANCIAL LOGIC (Phase 5 Standard)
# ══════════════════════════════════════════════════════════════════════

def compute_totals(username: str) -> dict:
    """
    Standard Financial Calculation:
      Available Balance = Total Income − Total Expenses − Net Savings Contributions

    Rules:
      1. Savings transfers must NOT count as ordinary expenses.
      2. Savings withdrawals must NOT count as income.
      3. Prevent double counting.
    """
    rows = csv_storage.get_user_transactions(username)
    goals = csv_storage.get_user_goals(username)

    total_income = sum(t["amount"] for t in rows if t["type"] == "income")
    total_expenses = sum(t["amount"] for t in rows if t["type"] == "expense")
    total_saved = sum(g["saved"] for g in goals)

    # Net liquid balance remaining
    available = total_income - total_expenses - total_saved

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_saved": total_saved,
        "available": available,
    }


def get_expense_by_category(username: str) -> dict:
    """Aggregate expenses by category for pie/doughnut charts."""
    rows = csv_storage.get_user_transactions(username)
    result = defaultdict(float)
    for t in rows:
        if t["type"] == "expense":
            result[t["category"]] += t["amount"]
    return dict(result)


def get_income_by_category(username: str) -> dict:
    """Aggregate income by source for pie/doughnut charts."""
    rows = csv_storage.get_user_transactions(username)
    result = defaultdict(float)
    for t in rows:
        if t["type"] == "income":
            result[t["category"]] += t["amount"]
    return dict(result)


def get_monthly_data(username: str) -> list:
    """
    Calculate chronological monthly income vs expenses for bar/line charts.
    Returns: list of dicts: [{month: 'Jan 2026', income: float, expenses: float, net: float}]
    """
    rows = csv_storage.get_user_transactions(username)
    # Use sort key for chronological accuracy: YYYY-MM
    monthly_dict = defaultdict(lambda: {"income": 0.0, "expenses": 0.0, "sort_key": ""})

    for t in rows:
        try:
            dt = datetime.strptime(t["date"], "%Y-%m-%d")
            month_label = dt.strftime("%b %Y")
            sort_key = dt.strftime("%Y-%m")
        except (ValueError, TypeError):
            continue

        monthly_dict[month_label]["sort_key"] = sort_key
        if t["type"] == "income":
            monthly_dict[month_label]["income"] += t["amount"]
        elif t["type"] == "expense":
            monthly_dict[month_label]["expenses"] += t["amount"]

    # Sort chronologically by YYYY-MM
    sorted_items = sorted(monthly_dict.items(), key=lambda item: item[1]["sort_key"])

    result = []
    for month_label, vals in sorted_items:
        net = vals["income"] - vals["expenses"]
        result.append({
            "month": month_label,
            "income": round(vals["income"], 2),
            "expenses": round(vals["expenses"], 2),
            "net": round(net, 2),
        })
    return result


def get_budget_status(username: str) -> list:
    """
    Compare category budgets against real CSV expense transactions.
    Returns: [{category, budget, spent, remaining, pct}]
    """
    user_budgets = csv_storage.get_user_budgets(username)
    spent_by_cat = get_expense_by_category(username)
    result = []

    for cat, budget_amt in user_budgets.items():
        spent = spent_by_cat.get(cat, 0.0)
        remaining = budget_amt - spent
        pct = (spent / budget_amt * 100) if budget_amt > 0 else 0.0
        result.append({
            "category": cat,
            "budget": budget_amt,
            "spent": spent,
            "remaining": remaining,
            "pct": round(pct, 1),
        })
    return sorted(result, key=lambda x: x["pct"], reverse=True)


def fmt_inr(amount: float) -> str:
    """Global template filter: formats floats as Indian Rupee strings."""
    try:
        amt = round(float(amount), 2)
    except (ValueError, TypeError):
        return "₹0.00"

    is_negative = amt < 0
    amt = abs(amt)
    s = f"{amt:.2f}"
    integer_part, decimal_part = s.split(".")

    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        integer_part = ",".join(groups) + "," + last3

    formatted = f"₹{integer_part}.{decimal_part}"
    return f"-{formatted}" if is_negative else formatted


# Register template globals
app.jinja_env.globals["fmt_inr"] = fmt_inr
app.jinja_env.globals["today"] = date.today


# ══════════════════════════════════════════════════════════════════════
# ROUTES — AUTHENTICATION (users.csv)
# ══════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html")

        # Query CSV storage
        user = csv_storage.get_user_by_username(username)
        if not user:
            flash("Account not found. Please register first.", "error")
            return render_template("login.html")

        if not check_password(password, user.get("password_hash", "")):
            flash("Incorrect password. Please try again.", "error")
            return render_template("login.html")

        # Session established
        session["username"] = user["username"]
        session["full_name"] = user.get("full_name") or user["username"]
        flash(f"Welcome back, {session['full_name']}! 👋", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "username" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not email or "@" not in email:
            errors.append("A valid email address is required.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if csv_storage.get_user_by_username(username):
            errors.append("Username is already taken. Please choose another.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("register.html", full_name=full_name, username=username, email=email)

        # Write user to users.csv
        p_hash = hash_password(password)
        success = csv_storage.add_user(username, full_name, email, p_hash)
        if success:
            flash("Account created successfully! Please sign in. ✅", "success")
            return redirect(url_for("login"))
        else:
            flash("Failed to create account. Please try again.", "error")
            return render_template("register.html")

    return render_template("register.html")


@app.route("/logout")
def logout():
    name = session.get("full_name", "User")
    session.clear()
    flash(f"You have been logged out. Goodbye, {name}! 👋", "info")
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════════════
# ROUTES — DASHBOARD (Real CSV Data)
# ══════════════════════════════════════════════════════════════════════

@app.route("/dashboard")
@login_required
def dashboard():
    username = current_user()
    totals = compute_totals(username)
    all_txs = csv_storage.get_user_transactions(username)
    recent_tx = all_txs[:5]
    budget_status = get_budget_status(username)[:3]
    goals = csv_storage.get_user_goals(username)[:4]

    monthly = get_monthly_data(username)
    chart_labels = [m["month"] for m in monthly]
    chart_income = [m["income"] for m in monthly]
    chart_expenses = [m["expenses"] for m in monthly]

    exp_cats = get_expense_by_category(username)

    return render_template(
        "dashboard.html",
        totals=totals,
        recent_tx=recent_tx,
        budget_status=budget_status,
        goals=goals,
        chart_labels=chart_labels,
        chart_income=chart_income,
        chart_expenses=chart_expenses,
        exp_cats=exp_cats,
    )


# ══════════════════════════════════════════════════════════════════════
# ROUTES — INCOME (transactions.csv)
# ══════════════════════════════════════════════════════════════════════

@app.route("/income", methods=["GET", "POST"])
@login_required
def income():
    username = current_user()

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        tx_date = request.form.get("date", "").strip()

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Income amount must be greater than zero.", "error")
            return redirect(url_for("income"))

        if not category:
            flash("Please choose an income category.", "error")
            return redirect(url_for("income"))

        try:
            csv_storage.add_transaction(username, "income", amount, category, description, tx_date)
            flash(f"Income of ₹{amount:,.2f} recorded in transactions.csv! 💰", "success")
        except Exception as e:
            flash(f"Error saving income: {e}", "error")

        return redirect(url_for("income"))

    all_txs = csv_storage.get_user_transactions(username)
    income_rows = [t for t in all_txs if t["type"] == "income"]
    income_cats = get_income_by_category(username)
    total_income = sum(t["amount"] for t in income_rows)
    monthly = get_monthly_data(username)

    return render_template(
        "income.html",
        income_rows=income_rows,
        income_cats=income_cats,
        total_income=total_income,
        monthly=monthly,
    )


# ══════════════════════════════════════════════════════════════════════
# ROUTES — EXPENSE (transactions.csv)
# ══════════════════════════════════════════════════════════════════════

@app.route("/expense", methods=["GET", "POST"])
@login_required
def expense():
    username = current_user()

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        tx_date = request.form.get("date", "").strip()

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Expense amount must be greater than zero.", "error")
            return redirect(url_for("expense"))

        if not category:
            flash("Please select an expense category.", "error")
            return redirect(url_for("expense"))

        try:
            csv_storage.add_transaction(username, "expense", amount, category, description, tx_date)
            flash(f"Expense of ₹{amount:,.2f} recorded in transactions.csv! 💸", "success")
        except Exception as e:
            flash(f"Error saving expense: {e}", "error")

        return redirect(url_for("expense"))

    all_txs = csv_storage.get_user_transactions(username)
    expense_rows = [t for t in all_txs if t["type"] == "expense"]
    expense_cats = get_expense_by_category(username)
    total_expenses = sum(t["amount"] for t in expense_rows)
    monthly = get_monthly_data(username)

    return render_template(
        "expense.html",
        expense_rows=expense_rows,
        expense_cats=expense_cats,
        total_expenses=total_expenses,
        monthly=monthly,
    )


# ══════════════════════════════════════════════════════════════════════
# ROUTES — BUDGETS (budgets.csv)
# ══════════════════════════════════════════════════════════════════════

@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    username = current_user()

    if request.method == "POST":
        action = request.form.get("action", "set")

        if action == "delete":
            category = request.form.get("category", "").strip()
            if csv_storage.delete_budget(username, category):
                flash(f"Budget for '{category}' removed from budgets.csv.", "info")
            else:
                flash(f"Could not remove budget for '{category}'.", "error")
            return redirect(url_for("budget"))

        # Set / Update budget
        category = request.form.get("category", "").strip()
        amount_raw = request.form.get("amount", "").strip()

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Budget amount must be a positive number.", "error")
            return redirect(url_for("budget"))

        if not category:
            flash("Please select a category.", "error")
            return redirect(url_for("budget"))

        try:
            csv_storage.set_budget(username, category, amount)
            flash(f"Budget for '{category}' set to ₹{amount:,.2f} in budgets.csv! 🎯", "success")
        except Exception as e:
            flash(f"Error setting budget: {e}", "error")

        return redirect(url_for("budget"))

    budget_status = get_budget_status(username)
    total_budgeted = sum(b["budget"] for b in budget_status)
    total_spent = sum(b["spent"] for b in budget_status)
    over_budget = [b for b in budget_status if b["pct"] > 100]

    return render_template(
        "budget.html",
        budget_status=budget_status,
        total_budgeted=total_budgeted,
        total_spent=total_spent,
        over_budget=over_budget,
    )


# ══════════════════════════════════════════════════════════════════════
# ROUTES — SAVINGS GOALS (savings_goals.csv & monthly_transfers.csv)
# ══════════════════════════════════════════════════════════════════════

@app.route("/savings", methods=["GET", "POST"])
@login_required
def savings():
    username = current_user()

    if request.method == "POST":
        action = request.form.get("action", "create")

        # ── Create New Goal ──
        if action == "create":
            goal_name = request.form.get("goal_name", "").strip()
            target_raw = request.form.get("target", "").strip()
            initial_raw = request.form.get("initial", "0").strip() or "0"

            try:
                target = float(target_raw)
                if target <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                flash("Goal target must be a positive number.", "error")
                return redirect(url_for("savings"))

            try:
                initial = float(initial_raw)
                if initial < 0:
                    initial = 0.0
            except (ValueError, TypeError):
                initial = 0.0

            try:
                csv_storage.add_goal(username, goal_name, target, initial)
                flash(f"Savings goal '{goal_name}' created in savings_goals.csv! 🏦", "success")
            except Exception as e:
                flash(f"Could not create goal: {e}", "error")

        # ── Deposit to Existing Goal ──
        elif action == "deposit":
            goal_id = request.form.get("goal_id", "").strip()
            amount_raw = request.form.get("amount", "").strip()

            try:
                amount = float(amount_raw)
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                flash("Deposit amount must be greater than zero.", "error")
                return redirect(url_for("savings"))

            totals = compute_totals(username)
            if amount > totals["available"]:
                flash("Insufficient available balance for this savings transfer.", "error")
                return redirect(url_for("savings"))

            try:
                if csv_storage.deposit_to_goal(username, goal_id, amount):
                    flash(f"Transferred ₹{amount:,.2f} to savings goal! Logged in monthly_transfers.csv. 💸", "success")
                else:
                    flash("Goal not found.", "error")
            except Exception as e:
                flash(f"Transfer error: {e}", "error")

        # ── Withdraw from Goal ──
        elif action == "withdraw":
            goal_id = request.form.get("goal_id", "").strip()
            amount_raw = request.form.get("amount", "").strip()

            try:
                amount = float(amount_raw)
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                flash("Withdrawal amount must be greater than zero.", "error")
                return redirect(url_for("savings"))

            try:
                if csv_storage.withdraw_from_goal(username, goal_id, amount):
                    flash(f"Withdrew ₹{amount:,.2f} from goal back to available balance! (Not counted as income) 🏧", "success")
                else:
                    flash("Goal not found.", "error")
            except ValueError as ve:
                flash(str(ve), "error")
            except Exception as e:
                flash(f"Withdrawal error: {e}", "error")

        # ── Delete Goal ──
        elif action == "delete":
            goal_id = request.form.get("goal_id", "").strip()
            if csv_storage.delete_goal(username, goal_id):
                flash("Savings goal deleted from savings_goals.csv.", "info")
            else:
                flash("Could not delete savings goal.", "error")

        return redirect(url_for("savings"))

    raw_goals = csv_storage.get_user_goals(username)
    totals = compute_totals(username)

    goals = []
    for g in raw_goals:
        pct = (g["saved"] / g["target"] * 100) if g["target"] > 0 else 0
        goals.append({**g, "pct": round(pct, 1)})

    return render_template(
        "savings.html",
        goals=goals,
        totals=totals,
    )


# ══════════════════════════════════════════════════════════════════════
# ROUTES — TRANSACTIONS (CRUD in transactions.csv)
# ══════════════════════════════════════════════════════════════════════

@app.route("/transactions")
@login_required
def transactions():
    username = current_user()
    tx_type = request.args.get("type", "").strip().lower()
    search = request.args.get("search", "").strip().lower()

    all_tx = csv_storage.get_user_transactions(username)

    if tx_type:
        all_tx = [t for t in all_tx if t["type"] == tx_type]
    if search:
        all_tx = [t for t in all_tx
                  if search in t["description"].lower()
                  or search in t["category"].lower()
                  or search in t["id"].lower()]

    totals = compute_totals(username)
    all_raw = csv_storage.get_user_transactions(username)
    income_count = sum(1 for t in all_raw if t["type"] == "income")
    expense_count = sum(1 for t in all_raw if t["type"] == "expense")
    savings_count = len(csv_storage.get_user_goals(username))

    return render_template(
        "transactions.html",
        transactions=all_tx,
        totals=totals,
        tx_type=tx_type,
        search=search,
        income_count=income_count,
        expense_count=expense_count,
        savings_count=savings_count,
    )


@app.route("/delete_transaction/<tx_id>", methods=["POST"])
@login_required
def delete_transaction(tx_id):
    username = current_user()
    if csv_storage.delete_transaction(username, tx_id):
        flash(f"Transaction #{tx_id} deleted from transactions.csv. 🗑️", "success")
    else:
        flash("Transaction not found or unauthorized.", "error")
    
    # Return to previous page or transactions list
    referrer = request.referrer
    if referrer and ("income" in referrer or "expense" in referrer):
        return redirect(referrer)
    return redirect(url_for("transactions"))


@app.route("/edit_transaction/<tx_id>", methods=["POST"])
@login_required
def edit_transaction(tx_id):
    username = current_user()
    kind = request.form.get("type", "").strip().lower()
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    tx_date = request.form.get("date", "").strip()

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash("Invalid transaction amount.", "error")
        return redirect(url_for("transactions"))

    try:
        success = csv_storage.update_transaction(username, tx_id, kind, amount, category, description, tx_date)
        if success:
            flash(f"Transaction #{tx_id} updated successfully in CSV! ✏️", "success")
        else:
            flash("Transaction could not be found to update.", "error")
    except Exception as e:
        flash(f"Error updating transaction: {e}", "error")

    return redirect(url_for("transactions"))


# ══════════════════════════════════════════════════════════════════════
# ROUTES — REPORTS (Real CSV Analytics)
# ══════════════════════════════════════════════════════════════════════

@app.route("/reports")
@login_required
def reports():
    username = current_user()
    totals = compute_totals(username)
    monthly = get_monthly_data(username)

    annual_income = sum(m["income"] for m in monthly)
    annual_expenses = sum(m["expenses"] for m in monthly)
    annual_net = annual_income - annual_expenses
    savings_rate = (annual_net / annual_income * 100) if annual_income > 0 else 0.0

    chart_labels = [m["month"] for m in monthly]
    chart_income = [m["income"] for m in monthly]
    chart_expenses = [m["expenses"] for m in monthly]

    exp_cats = get_expense_by_category(username)
    inc_cats = get_income_by_category(username)
    goals = csv_storage.get_user_goals(username)

    return render_template(
        "reports.html",
        totals=totals,
        monthly=monthly,
        annual_income=annual_income,
        annual_expenses=annual_expenses,
        annual_net=annual_net,
        savings_rate=round(savings_rate, 1),
        chart_labels=chart_labels,
        chart_income=chart_income,
        chart_expenses=chart_expenses,
        exp_cats=exp_cats,
        inc_cats=inc_cats,
        goals=goals,
    )


# ══════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# Vercel Serverless WSGI entry point
handler = app

# ══════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1")
    print("=" * 65)
    print("  Aurora Finance Tracker — Live Server")
    print("  Connected to CSV Storage in: data/*.csv")
    print(f"  Application running at: http://127.0.0.1:{port}")
    print("  Press Ctrl+C to terminate server")
    print("=" * 65)
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
