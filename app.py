from flask import Flask, render_template, request, redirect, session, jsonify
from flask_pymongo import PyMongo
from datetime import datetime
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "secret123"

# ✅ MongoDB Configuration
# Note: Keep your URI secure. In a production app, use environment variables.
app.config["MONGO_URI"] = "mongodb+srv://onkarghadage1107_db_user:cPfYrgcDoaCdkOlz@cluster0.gs7ggdy.mongodb.net/yourtreasurer"

mongo = PyMongo(app)

# Database Collections
users = mongo.db.users
expenses = mongo.db.expenses
loans = mongo.db.loans


# ---------------- LOGIN / REGISTER ---------------- #

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')
        limit = request.form.get('monthly_limit', 0)

        user = users.find_one({"name": name})

        # If user doesn't exist, create a new profile
        if not user:
            users.insert_one({
                "name": name,
                "password": password, # In a real app, use werkzeug.security to hash this!
                "monthly_limit": int(limit),
                "current_spend": 0
            })
            session['user'] = name
            return redirect('/')

        # Check existing user password
        if user['password'] == password:
            session['user'] = name
            return redirect('/')
        else:
            return "Invalid Password" # Simple error handling

    return render_template("profile.html")


# ---------------- HOME / DASHBOARD ---------------- #

@app.route('/')
def home():
    if "user" not in session:
        return redirect('/login')
    return render_template("index.html", user=session.get("user"))


# ---------------- API FOR PROGRESS ---------------- #

@app.route('/api/progress')
def progress():
    if "user" not in session:
        return jsonify({"progress": 0, "spent": 0, "limit": 0})

    user = users.find_one({"name": session["user"]})
    if not user:
        return jsonify({"progress": 0})

    spent = user.get("current_spend", 0)
    limit = user.get("monthly_limit", 1) # Prevent division by zero

    # Calculate percentage
    percent = (spent / limit) * 100

    return jsonify({
        "progress": round(percent, 2),
        "spent": spent,
        "limit": limit
    })


# ---------------- EXPENSE PAGE ---------------- #

@app.route('/my_expenses')
def my_expenses():
    if "user" not in session:
        return redirect('/login')

    # Get all expenses and loans for the logged-in user
    exp_list = list(expenses.find({"user": session["user"]}).sort("date", -1))
    loan_data = list(loans.find({"user": session["user"]}))

    return render_template("expenses.html", expenses=exp_list, loans=loan_data)


# ---------------- ADD EXPENSE ---------------- #

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if "user" not in session:
        return redirect('/login')

    amount = int(request.form.get('amount', 0))
    category = request.form.get('category', 'General')

    # Record the expense
    expenses.insert_one({
        "user": session["user"],
        "amount": amount,
        "category": category,
        "date": datetime.now()
    })

    # Update the user's total current spend
    users.update_one(
        {"name": session["user"]},
        {"$inc": {"current_spend": amount}}
    )

    return redirect('/my_expenses')


# ---------------- ADD LOAN ---------------- #

@app.route('/add_loan', methods=['POST'])
def add_loan():
    if "user" not in session:
        return redirect('/login')

    loans.insert_one({
        "user": session["user"],
        "friend_name": request.form.get('friend_name'),
        "amount": int(request.form.get('amount', 0)),
        "status": "pending"
    })
    return redirect('/my_expenses')


# ---------------- MARK RETURNED ---------------- #

@app.route('/mark_returned/<loan_id>', methods=['POST'])
def mark_returned(loan_id):
    if "user" not in session:
        return redirect('/login')

    # Find the loan details before updating
    loan = loans.find_one({"_id": ObjectId(loan_id)})
    
    if loan and loan['status'] == 'pending':
        # Update loan status
        loans.update_one(
            {"_id": ObjectId(loan_id)},
            {"$set": {"status": "returned"}}
        )

        amount = loan['amount']

        # Recording a 'negative' expense because money came back to you
        expenses.insert_one({
            "user": session["user"],
            "amount": -amount,
            "category": f"Loan Return: {loan['friend_name']}",
            "date": datetime.now()
        })

        # Decrease current spending since debt was repaid
        users.update_one(
            {"name": session["user"]},
            {"$inc": {"current_spend": -amount}}
        )

    return redirect('/my_expenses')


# ---------------- LOGOUT ---------------- #

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


if __name__ == "__main__":
    # In production, set debug=False
    app.run(debug=True)