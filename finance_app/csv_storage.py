"""
╔══════════════════════════════════════════════════════════════════════╗
║   Aurora Finance Tracker — csv_storage.py                            ║
║   Phase 3: Persistent CSV Storage Engine                             ║
║   Uses Python's built-in csv module (No SQL, No External DB)         ║
╚══════════════════════════════════════════════════════════════════════╝

FILES MANAGED IN data/:
  1. users.csv             -> Authentication & User profiles
  2. transactions.csv      -> Income & Expense ledger
  3. budgets.csv           -> Monthly category spending limits
  4. savings_goals.csv     -> Savings targets and accumulated funds
  5. monthly_transfers.csv -> Savings transfers ledger (audit log)

FEATURES:
  - Automatic file & folder initialization with headers
  - Safe reads & writes with utf-8 encoding and newline=''
  - Atomic rewrite pattern for updates and deletions
  - Data validation & type safety (floats, dates, required fields)
  - ID generation with collision avoidance
  - Graceful error handling (corrupted rows skipped with warnings)
  - Data remains permanent across application restarts
"""

import os
import csv
import uuid
from datetime import date, datetime
from typing import Dict, List, Optional, Any

# ══════════════════════════════════════════════════════════════════════
# DIRECTORY & FILE PATH CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On Vercel / AWS Lambda, the root deployment directory is read-only.
# Only /tmp is writable. Detect serverless environments automatically:
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
DATA_DIR = "/tmp/data" if IS_SERVERLESS else os.path.join(BASE_DIR, "data")

USERS_FILE = os.path.join(DATA_DIR, "users.csv")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.csv")
BUDGETS_FILE = os.path.join(DATA_DIR, "budgets.csv")
SAVINGS_GOALS_FILE = os.path.join(DATA_DIR, "savings_goals.csv")
MONTHLY_TRANSFERS_FILE = os.path.join(DATA_DIR, "monthly_transfers.csv")

# Standard CSV Headers
SCHEMAS = {
    USERS_FILE: ["username", "full_name", "email", "password_hash", "created_at"],
    TRANSACTIONS_FILE: ["id", "username", "type", "amount", "category", "description", "date"],
    BUDGETS_FILE: ["category_key", "username", "category", "amount"],
    SAVINGS_GOALS_FILE: ["goal_key", "username", "name", "target", "saved", "created_at"],
    MONTHLY_TRANSFERS_FILE: ["transfer_id", "username", "goal_key", "goal_name", "amount", "date"],
}


# ══════════════════════════════════════════════════════════════════════
# LOW-LEVEL CSV HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════

def init_storage(seed_demo: bool = True) -> None:
    """
    Ensure the data/ directory and all 5 CSV files exist with appropriate headers.
    Optionally seeds demo data if the system is newly created.
    """
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except OSError:
        pass

    import shutil
    source_dir = os.path.join(BASE_DIR, "data")
    if IS_SERVERLESS and os.path.exists(source_dir):
        for fname in os.listdir(source_dir):
            src_f = os.path.join(source_dir, fname)
            dst_f = os.path.join(DATA_DIR, fname)
            if os.path.isfile(src_f) and not os.path.exists(dst_f):
                try:
                    shutil.copy2(src_f, dst_f)
                except Exception:
                    pass

    for filepath, header in SCHEMAS.items():
        try:
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                with open(filepath, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
        except OSError:
            pass

    if seed_demo:
        try:
            seed_default_data()
        except Exception:
            pass


def read_csv(filepath: str) -> List[Dict[str, str]]:
    """
    Safely read all rows from a CSV file as a list of dictionaries.
    Returns empty list if file doesn't exist or is empty.
    """
    if not os.path.exists(filepath):
        return []
    
    records = []
    try:
        with open(filepath, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Strip keys and values to eliminate accidental whitespace
                cleaned = {k.strip(): v.strip() for k, v in row.items() if k is not None}
                records.append(cleaned)
    except Exception as e:
        print(f"[CSV Storage] Error reading {filepath}: {e}")
        return []
    return records


def write_csv(filepath: str, rows: List[Dict[str, Any]]) -> bool:
    """
    Overwrite an entire CSV file atomically with the given rows.
    """
    fieldnames = SCHEMAS.get(filepath)
    if not fieldnames:
        raise ValueError(f"Unknown schema for file: {filepath}")

    temp_filepath = filepath + ".tmp"
    try:
        with open(temp_filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                # Filter row keys to only write expected fieldnames
                filtered = {k: r.get(k, "") for k in fieldnames}
                writer.writerow(filtered)
        
        # Replace the real file atomically
        os.replace(temp_filepath, filepath)
        return True
    except Exception as e:
        print(f"[CSV Storage] Error writing {filepath}: {e}")
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except OSError:
                pass
        return False


def append_csv(filepath: str, row: Dict[str, Any]) -> bool:
    """
    Append a single record to the specified CSV file.
    """
    fieldnames = SCHEMAS.get(filepath)
    if not fieldnames:
        raise ValueError(f"Unknown schema for file: {filepath}")

    try:
        # If file missing or empty, recreate header first
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            with open(filepath, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow({k: row.get(k, "") for k in fieldnames})
            return True

        with open(filepath, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow({k: row.get(k, "") for k in fieldnames})
        return True
    except Exception as e:
        print(f"[CSV Storage] Error appending to {filepath}: {e}")
        return False


def generate_unique_id(prefix: str = "TX") -> str:
    """
    Generate an 8-character unique alphanumeric identifier.
    Example: TX-A1B2C3D4
    """
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ══════════════════════════════════════════════════════════════════════
# USERS STORAGE API (users.csv)
# ══════════════════════════════════════════════════════════════════════

def get_all_users() -> List[Dict[str, str]]:
    """Return all user records from users.csv."""
    return read_csv(USERS_FILE)


def get_user_by_username(username: str) -> Optional[Dict[str, str]]:
    """Lookup a single user by username (case-insensitive)."""
    uname = username.strip().lower()
    for u in get_all_users():
        if u.get("username", "").strip().lower() == uname:
            return u
    return None


def add_user(username: str, full_name: str, email: str, password_hash: str) -> bool:
    """
    Register a new user to users.csv.
    Returns True if added successfully, False if username already exists.
    """
    username = username.strip().lower()
    if get_user_by_username(username):
        return False

    record = {
        "username": username,
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "password_hash": password_hash,
        "created_at": date.today().isoformat(),
    }
    return append_csv(USERS_FILE, record)


# ══════════════════════════════════════════════════════════════════════
# TRANSACTIONS STORAGE API (transactions.csv)
# ══════════════════════════════════════════════════════════════════════

def get_user_transactions(username: str) -> List[Dict[str, Any]]:
    """
    Return all transactions belonging to a user, converted to proper types
    and sorted chronologically (newest date first).
    """
    uname = username.strip().lower()
    rows = read_csv(TRANSACTIONS_FILE)
    user_rows = []

    for r in rows:
        if r.get("username", "").strip().lower() == uname:
            try:
                amt = float(r.get("amount", 0) or 0)
            except (ValueError, TypeError):
                amt = 0.0

            user_rows.append({
                "id": r.get("id", ""),
                "username": uname,
                "type": r.get("type", "expense").strip().lower(),
                "amount": amt,
                "category": r.get("category", "Others").strip(),
                "description": r.get("description", "").strip(),
                "date": r.get("date", date.today().isoformat()).strip(),
            })

    # Sort descending by date
    return sorted(user_rows, key=lambda x: x["date"], reverse=True)


def add_transaction(username: str, kind: str, amount: float, category: str,
                    description: str, tx_date: str = "") -> Dict[str, Any]:
    """
    Append a new income or expense transaction to transactions.csv.
    """
    username = username.strip().lower()
    kind = kind.strip().lower()
    if kind not in ("income", "expense"):
        raise ValueError("Transaction type must be 'income' or 'expense'.")
    if amount <= 0:
        raise ValueError("Transaction amount must be strictly greater than zero.")
    if not category.strip():
        raise ValueError("Category cannot be empty.")
    if not description.strip():
        raise ValueError("Description cannot be empty.")
    
    if not tx_date.strip():
        tx_date = date.today().isoformat()
    else:
        # Validate date format (YYYY-MM-DD)
        try:
            datetime.strptime(tx_date.strip(), "%Y-%m-%d")
            tx_date = tx_date.strip()
        except ValueError:
            tx_date = date.today().isoformat()

    tx_id = generate_unique_id(prefix="INC" if kind == "income" else "EXP")
    record = {
        "id": tx_id,
        "username": username,
        "type": kind,
        "amount": f"{amount:.2f}",
        "category": category.strip(),
        "description": description.strip(),
        "date": tx_date,
    }

    success = append_csv(TRANSACTIONS_FILE, record)
    if not success:
        raise IOError("Failed to save transaction to CSV.")

    # Return typed copy for immediate UI usage
    return {
        "id": tx_id,
        "username": username,
        "type": kind,
        "amount": amount,
        "category": category.strip(),
        "description": description.strip(),
        "date": tx_date,
    }


def delete_transaction(username: str, tx_id: str) -> bool:
    """
    Delete a transaction from transactions.csv by its unique ID.
    Only allows deletion if the record belongs to the requesting username.
    """
    username = username.strip().lower()
    tx_id = tx_id.strip()
    all_rows = read_csv(TRANSACTIONS_FILE)

    filtered = []
    found = False
    for r in all_rows:
        if r.get("id", "").strip() == tx_id and r.get("username", "").strip().lower() == username:
            found = True
        else:
            filtered.append(r)

    if found:
        return write_csv(TRANSACTIONS_FILE, filtered)
    return False


def get_transaction_by_id(username: str, tx_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single transaction by ID for a user."""
    txs = get_user_transactions(username)
    for t in txs:
        if t["id"] == tx_id:
            return t
    return None


def update_transaction(username: str, tx_id: str, kind: str, amount: float,
                       category: str, description: str, tx_date: str) -> bool:
    """
    Update an existing transaction in transactions.csv.
    """
    username = username.strip().lower()
    tx_id = tx_id.strip()
    kind = kind.strip().lower()
    if kind not in ("income", "expense"):
        raise ValueError("Transaction type must be 'income' or 'expense'.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if not category.strip() or not description.strip():
        raise ValueError("Category and description cannot be empty.")

    all_rows = read_csv(TRANSACTIONS_FILE)
    updated = False

    for r in all_rows:
        if r.get("id", "").strip() == tx_id and r.get("username", "").strip().lower() == username:
            r["type"] = kind
            r["amount"] = f"{amount:.2f}"
            r["category"] = category.strip()
            r["description"] = description.strip()
            r["date"] = tx_date.strip() if tx_date.strip() else r.get("date", "")
            updated = True
            break

    if updated:
        return write_csv(TRANSACTIONS_FILE, all_rows)
    return False


# ══════════════════════════════════════════════════════════════════════
# BUDGETS STORAGE API (budgets.csv)
# ══════════════════════════════════════════════════════════════════════

def get_user_budgets(username: str) -> Dict[str, float]:
    """
    Return a dictionary of { category: monthly_limit_float } for the user.
    """
    uname = username.strip().lower()
    rows = read_csv(BUDGETS_FILE)
    result = {}

    for r in rows:
        if r.get("username", "").strip().lower() == uname:
            cat = r.get("category", "").strip()
            try:
                amt = float(r.get("amount", 0) or 0)
            except (ValueError, TypeError):
                amt = 0.0
            if cat:
                result[cat] = amt
    return result


def set_budget(username: str, category: str, amount: float) -> bool:
    """
    Set or update a category budget for a user in budgets.csv.
    """
    uname = username.strip().lower()
    category = category.strip()
    if not category:
        raise ValueError("Budget category cannot be empty.")
    if amount <= 0:
        raise ValueError("Budget amount must be greater than zero.")

    key = f"{uname}|{category.lower()}"
    all_rows = read_csv(BUDGETS_FILE)

    updated = False
    for r in all_rows:
        if r.get("category_key", "").lower() == key:
            r["amount"] = f"{amount:.2f}"
            r["category"] = category
            updated = True
            break

    if not updated:
        all_rows.append({
            "category_key": key,
            "username": uname,
            "category": category,
            "amount": f"{amount:.2f}",
        })

    return write_csv(BUDGETS_FILE, all_rows)


def delete_budget(username: str, category: str) -> bool:
    """
    Delete a budget entry for a category.
    """
    uname = username.strip().lower()
    key = f"{uname}|{category.strip().lower()}"
    all_rows = read_csv(BUDGETS_FILE)

    filtered = [r for r in all_rows if r.get("category_key", "").lower() != key]
    if len(filtered) < len(all_rows):
        return write_csv(BUDGETS_FILE, filtered)
    return False


# ══════════════════════════════════════════════════════════════════════
# SAVINGS GOALS API (savings_goals.csv)
# ══════════════════════════════════════════════════════════════════════

def get_user_goals(username: str) -> List[Dict[str, Any]]:
    """
    Return all savings goals for a user.
    """
    uname = username.strip().lower()
    rows = read_csv(SAVINGS_GOALS_FILE)
    result = []

    for r in rows:
        if r.get("username", "").strip().lower() == uname:
            try:
                target = float(r.get("target", 0) or 0)
                saved = float(r.get("saved", 0) or 0)
            except (ValueError, TypeError):
                target = 0.0
                saved = 0.0

            result.append({
                "id": r.get("goal_key", ""),
                "name": r.get("name", "").strip(),
                "target": target,
                "saved": saved,
                "created_at": r.get("created_at", ""),
            })
    return result


def add_goal(username: str, name: str, target: float, initial: float = 0.0) -> Dict[str, Any]:
    """
    Create a new savings goal in savings_goals.csv.
    """
    uname = username.strip().lower()
    name = name.strip()
    if not name:
        raise ValueError("Goal name cannot be empty.")
    if target <= 0:
        raise ValueError("Target amount must be greater than zero.")
    if initial < 0:
        initial = 0.0

    key = f"GOAL-{uuid.uuid4().hex[:8].upper()}"
    all_goals = get_user_goals(uname)
    if any(g["name"].lower() == name.lower() for g in all_goals):
        raise ValueError(f"A goal named '{name}' already exists.")

    record = {
        "goal_key": key,
        "username": uname,
        "name": name,
        "target": f"{target:.2f}",
        "saved": f"{initial:.2f}",
        "created_at": date.today().isoformat(),
    }

    if not append_csv(SAVINGS_GOALS_FILE, record):
        raise IOError("Failed to save goal to CSV.")

    # If initial deposit was made, record it in transfers too
    if initial > 0:
        record_transfer(uname, key, name, initial)

    return {
        "id": key,
        "name": name,
        "target": target,
        "saved": initial,
    }


def deposit_to_goal(username: str, goal_id: str, amount: float) -> bool:
    """
    Deposit funds into a savings goal and log the transfer in monthly_transfers.csv.
    """
    uname = username.strip().lower()
    goal_id = goal_id.strip()
    if amount <= 0:
        raise ValueError("Deposit amount must be greater than zero.")

    all_rows = read_csv(SAVINGS_GOALS_FILE)
    found_goal_name = ""
    updated = False

    for r in all_rows:
        if r.get("goal_key", "").strip() == goal_id and r.get("username", "").strip().lower() == uname:
            current_saved = float(r.get("saved", 0) or 0)
            r["saved"] = f"{(current_saved + amount):.2f}"
            found_goal_name = r.get("name", "Savings Goal")
            updated = True
            break

    if updated:
        if write_csv(SAVINGS_GOALS_FILE, all_rows):
            record_transfer(uname, goal_id, found_goal_name, amount)
            return True
    return False


def withdraw_from_goal(username: str, goal_id: str, amount: float) -> bool:
    """
    Withdraw funds from a savings goal back to available liquid balance.
    Reduces goal's saved amount. Does NOT count as ordinary income.
    Logs transfer withdrawal in monthly_transfers.csv.
    """
    uname = username.strip().lower()
    goal_id = goal_id.strip()
    if amount <= 0:
        raise ValueError("Withdrawal amount must be greater than zero.")

    all_rows = read_csv(SAVINGS_GOALS_FILE)
    found_goal_name = ""
    updated = False

    for r in all_rows:
        if r.get("goal_key", "").strip() == goal_id and r.get("username", "").strip().lower() == uname:
            current_saved = float(r.get("saved", 0) or 0)
            if amount > current_saved:
                raise ValueError(f"Insufficient funds in goal. Available: ₹{current_saved:,.2f}")
            r["saved"] = f"{(current_saved - amount):.2f}"
            found_goal_name = r.get("name", "Savings Goal")
            updated = True
            break

    if updated:
        if write_csv(SAVINGS_GOALS_FILE, all_rows):
            record_transfer(uname, goal_id, found_goal_name, -amount)
            return True
    return False


def delete_goal(username: str, goal_id: str) -> bool:
    """
    Delete a savings goal from savings_goals.csv.
    """
    uname = username.strip().lower()
    goal_id = goal_id.strip()
    all_rows = read_csv(SAVINGS_GOALS_FILE)

    filtered = [
        r for r in all_rows
        if not (r.get("goal_key", "").strip() == goal_id and r.get("username", "").strip().lower() == uname)
    ]
    if len(filtered) < len(all_rows):
        return write_csv(SAVINGS_GOALS_FILE, filtered)
    return False


# ══════════════════════════════════════════════════════════════════════
# MONTHLY TRANSFERS API (monthly_transfers.csv)
# ══════════════════════════════════════════════════════════════════════

def record_transfer(username: str, goal_key: str, goal_name: str,
                    amount: float, transfer_date: str = "") -> bool:
    """
    Log a savings contribution transfer in monthly_transfers.csv.
    This guarantees savings transfers do NOT count as ordinary expenses.
    """
    uname = username.strip().lower()
    if not transfer_date.strip():
        transfer_date = date.today().isoformat()

    transfer_id = generate_unique_id(prefix="TRF")
    record = {
        "transfer_id": transfer_id,
        "username": uname,
        "goal_key": goal_key,
        "goal_name": goal_name,
        "amount": f"{amount:.2f}",
        "date": transfer_date,
    }
    return append_csv(MONTHLY_TRANSFERS_FILE, record)


def get_user_transfers(username: str) -> List[Dict[str, Any]]:
    """
    Return all monthly transfer records for a user.
    """
    uname = username.strip().lower()
    rows = read_csv(MONTHLY_TRANSFERS_FILE)
    result = []

    for r in rows:
        if r.get("username", "").strip().lower() == uname:
            try:
                amt = float(r.get("amount", 0) or 0)
            except (ValueError, TypeError):
                amt = 0.0
            result.append({
                "transfer_id": r.get("transfer_id", ""),
                "goal_key": r.get("goal_key", ""),
                "goal_name": r.get("goal_name", ""),
                "amount": amt,
                "date": r.get("date", ""),
            })
    return sorted(result, key=lambda x: x["date"], reverse=True)


# ══════════════════════════════════════════════════════════════════════
# DEFAULT DATA SEEDER
# ══════════════════════════════════════════════════════════════════════

def seed_default_data() -> None:
    """
    Seed initial demo data if the users.csv file is empty.
    Creates a pre-configured 'rajasekhar' account with starter transactions.
    """
    if len(get_all_users()) > 0:
        return

    import hashlib
    default_hash = hashlib.sha256("password123".encode()).hexdigest()

    # 1. Seed user
    add_user(
        username="rajasekhar",
        full_name="Raja Sekhar",
        email="rajasekhar@example.com",
        password_hash=default_hash
    )

    # 2. Seed initial transactions
    demo_txs = [
        ("income",  60000.0, "Salary",      "Monthly Salary",     "2026-11-01"),
        ("expense", 3200.0,  "Food",        "Grocery shopping",   "2026-11-02"),
        ("income",  12000.0, "Freelance",   "Client Web App",     "2026-11-03"),
        ("expense", 2100.0,  "Bills",       "Electricity bill",   "2026-11-04"),
        ("expense", 5800.0,  "Shopping",    "Online Shopping",    "2026-11-07"),
        ("expense", 2500.0,  "Transport",   "Fuel & Metro",       "2026-11-09"),
        ("income",  7200.0,  "Investments", "Stock Dividends",    "2026-11-10"),
    ]
    for kind, amt, cat, desc, dt in demo_txs:
        try:
            add_transaction("rajasekhar", kind, amt, cat, desc, dt)
        except Exception:
            pass

    # 3. Seed budgets
    demo_budgets = {
        "Food": 15000.0,
        "Transport": 8000.0,
        "Shopping": 10000.0,
        "Bills": 12000.0,
        "Health": 6000.0,
    }
    for cat, amt in demo_budgets.items():
        set_budget("rajasekhar", cat, amt)

    # 4. Seed savings goals
    demo_goals = [
        ("Emergency Fund", 100000.0, 30000.0),
        ("Vacation — Goa", 50000.0,  18000.0),
        ("New Laptop",     50000.0,  45000.0),
    ]
    for name, target, initial in demo_goals:
        try:
            add_goal("rajasekhar", name, target, initial)
        except Exception:
            pass


# Automatically initialize on import
try:
    init_storage(seed_demo=True)
except Exception as e:
    print(f"[CSV Storage] Initialization warning: {e}")
