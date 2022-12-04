# Imports
import os

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session

from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, sgd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["sgd"] = sgd

# Configure session to use filesystem
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 lib to use SQLite database
db = SQL("sqlite:///meme.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # select user's portfolio from database
    rows = db.execute(
        "SELECT * FROM portfolio WHERE userid = :id", id=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :id",
                      id=session["user_id"])

    # get current cash balance
    cash = cash[0]['cash']

    # total value of portfolio
    sum = cash

    # add stock name, current lookup value, and total value and translate to sgd
    for row in rows:
        look = lookup()
        row['name'] = look['name']
        row['price'] = look['price']
        row['total'] = row['price'] * row['amount']

        sum += row['total']

        row['price'] = sgd(row['price'])
        row['total'] = sgd(row['total'])

    return render_template("index.html", rows=rows, cash=sgd(cash), sum=sgd(sum))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy $SAM tokens"""

    # GET request
    if request.method == "GET":
        return render_template("buy.html")

    # POST request
    else:
        # get symbol and amount from form
        symbol = "SAM"
        amount = request.form.get("amount")
        print(amount)
        quote = lookup()

        # check if symbol is valid
        if quote == None:
            return apology("must provide valid stock symbol", 400)

        # check if amount is valid
        if not amount:
            return apology("must provide number of amount", 400)

        # check if amount is number
        if not amount.isdigit():
            return apology("You cannot purchase partial amount.", 400)

        # cast amount to int
        amount = int(amount)

        # if amount is not positive
        if amount <= 0:
            return apology("must provide positive integer", 400)

        # symbol to uppercase
        symbol = symbol.upper()
        purchase = quote['price'] * amount

        # select user's cash balance to check if they can afford purchase
        balance = db.execute(
            "SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        balance = balance[0]['cash']
        remainder = balance - purchase

        if remainder < 0:
            return apology("insufficient funds", 400)

        # query portfolio to check if user already owns amount of this stock
        row = db.execute("SELECT * FROM portfolio WHERE userid = :id AND symbol = :symbol",
                         id=session["user_id"], symbol=symbol)

        # if row doesn't exist yet
        if len(row) != 1:
            db.execute("INSERT INTO portfolio (userid, symbol) VALUES (:id, :symbol)",
                       id=session["user_id"], symbol=symbol)

        # get previous number of amount owned by user
        oldshares = db.execute("SELECT amount FROM portfolio WHERE userid = :id AND symbol = :symbol",
                               id=session["user_id"], symbol=symbol)
        oldshares = oldshares[0]["amount"]

        # update portfolio with new number of amount and cash balance
        newshares = oldshares + amount

        db.execute("UPDATE portfolio SET amount = :newshares WHERE userid = :id AND symbol = :symbol",
                   newshares=newshares, id=session["user_id"], symbol=symbol)

        db.execute("UPDATE users SET cash = :remainder WHERE id = :id",
                   remainder=remainder, id=session["user_id"])

        # update history table with purchase
        db.execute("INSERT INTO history (userid, symbol, amount, method, price) VALUES (:userid, :symbol, :amount, 'Buy', :price)",
                   userid=session["user_id"], symbol=symbol, amount=amount, price=quote['price'])

    # redirect to index
    return redirect("/")


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """ Change Password """

    # GET request
    if request.method == "GET":
        return render_template("password.html")

    # POST request
    else:
        # if form is not complete
        if not request.form.get("oldpass") or not request.form.get("newpass") or not request.form.get("confirmation"):
            return apology("missing old or new password", 400)

        # get info from form
        oldpass = request.form.get("oldpass")
        newpass = request.form.get("newpass")
        confirmation = request.form.get("confirmation")

        # get the old password from the database
        hash = db.execute(
            "SELECT hash FROM users WHERE id = :id", id=session["user_id"])
        hash = hash[0]['hash']

        # check if old password is correct
        if not check_password_hash(hash, oldpass):
            return apology("old password incorrect", 400)

        # check if new password and confirmation match
        if newpass != confirmation:
            return apology("new passwords do not match", 400)

        # hash new password
        hash = generate_password_hash(confirmation)

        # update database with new password
        db.execute("UPDATE users SET hash = :hash WHERE id = :id",
                   hash=hash, id=session["user_id"])

        return redirect("/logout")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute(
        "SELECT * FROM history WHERE userid = :userid", userid=session["user_id"])

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget user info
    session.clear()

    # POST request
    if request.method == "POST":

        # username was submitted?
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # password was submitted?
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # get username from database
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect
        return redirect("/")

    # GET request
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user info
    session.clear()

    # redirect
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # GET request to quote.html
    if request.method == "GET":
        return render_template("quote.html")

    # POST request
    else:

        # lookup ticker symbol
        symbol = lookup()

        # if symbol is invalid
        if symbol == None:
            return apology("invalid stock symbol", 400)

        # return template quote.html with symbol info
        return render_template("quoted.html", symbol=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget user info
    session.clear()

    # POST request
    if request.method == "POST":

        # username was submitted?
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # password was submitted?
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # password confirmation was submitted and matches password?
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # hash password
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        # is username already taken?
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)
        if len(rows) != 0:
            return apology("username is already taken", 400)

        # if not, insert new user into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                   username=username, hash=hash)

        # redirect
        return redirect("/")

    # GET request
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell $SAM tokens"""

    # GET request
    if request.method == "GET":

        # get list of stocks in portfolio for user
        portfolio = db.execute("SELECT symbol FROM portfolio WHERE userid = :id",
                               id=session["user_id"])

        # render template with list of stocks
        return render_template("sell.html", portfolio=portfolio)

    # POST request
    else:
        # get info from form
        symbol = "SAM"
        amount = request.form.get("amount")

        # check if amount is number
        if not amount.isdigit():
            return apology("You cannot sell partial amount.", 400)

        amount = int(amount)

        # if amount is not positive
        if amount <= 0:
            return apology("must provide positive integer", 400)

        # lookup stock info
        quote = lookup()
        rows = db.execute("SELECT * FROM portfolio WHERE userid = :id AND symbol = :symbol",
                          id=session["user_id"], symbol=symbol)

        # return apology if symbol or number of amount is invalid
        if len(rows) != 1:
            return apology("must provide valid stock symbol", 400)

        if not amount:
            return apology("must provide number of amount", 400)

        # convert number of amount to integer
        oldshares = rows[0]['amount']
        amount = int(amount)

        # if owned amount is less than number of amount to sell
        if amount > oldshares:
            return apology("amount sold can't exceed amount owned", 400)

        # get the total value of the sale
        sold = quote['price'] * amount

        # update cash balance accordingly
        cash = db.execute(
            "SELECT cash FROM users WHERE id = :id", id=session['user_id'])
        cash = cash[0]['cash']
        cash = cash + sold

        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                   cash=cash, id=session["user_id"])

        # new number of amount
        newshares = oldshares - amount

        # if new number of amount is 0, delete stock from portfolio
        # else update number of amount
        if newshares > 0:
            db.execute("UPDATE portfolio SET amount = :newshares WHERE userid = :id AND symbol = :symbol",
                       newshares=newshares, id=session["user_id"], symbol=symbol)
        else:
            db.execute("DELETE FROM portfolio WHERE symbol = :symbol AND userid = :id",
                       symbol=symbol, id=session["user_id"])

        # update history table
        db.execute("INSERT INTO history (userid, symbol, amount, method, price) VALUES (:userid, :symbol, :amount, 'Sell', :price)",
                   userid=session["user_id"], symbol=symbol, amount=amount, price=quote['price'])

        # redirect
        return redirect("/")


@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    """Delete user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation was submitted and matches password
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE id = ?",
                          session["user_id"])

        # Ensure username exists, password is correct, and confirmation matches password
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")) or request.form.get("password") != request.form.get("confirmation"):
            return apology("invalid password and/or confirmation", 400)

        # Delete user from database
        db.execute("DELETE FROM users WHERE id = ?", session["user_id"])

        # Forget any user_id
        session.clear()

        # Redirect user to login form
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("delete.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == "__main__":
    app.run(debug=True)
