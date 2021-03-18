import os
import requests
import urllib.parse
import datetime

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
from dataclasses import dataclass
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash


###### CONFIGURATION ######
# Initialize Flask App Ojbect
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

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure Heroku Postgres database
db = SQL(os.getenv('DATABASE_URL'))

# Import Authorized User List
authusers = []
authusers.append(os.getenv('USERA'))
authusers.append(os.getenv('USERB'))

###### DATA STRUCTURES ######
# Set type variables
# Loteria
colors = ['black', 'red', 'turquoise', 'yellow', 'green', 'purple']
sizes = ['s', 'm', 'l']
loterias = {
    'La Dama': ['Frida', 'Frida Flowers'],
    'La Sirena': ['Mermaid Body', 'Mermaid Hair', 'Mermaid Tail'],
    'La Mano': ['Hand', 'Hand Swirls'],
    'La Bota': ['Boot', 'Boot Swirls', 'Boot Flames'],
    'El Corazon': ['Heart', 'Heart Swirls'],
    'El Musico': ['Guitar', 'Guitar Hands'],
    'La Estrella': ['Star', 'Star Swirls'],
    'El Pulpo': ['Octopus', 'Octopus Swirls', 'Octopus Tentacles'],
    'La Rosa': ['Rose', 'Rose Swirls', 'Rose Leaves'],
    'La Calavera': ['Skull', 'Skull Flames', 'Skull Swirls'],
    'El Poder': ['Fist', 'Fist Swirls', 'Fist Wrist']
}

@dataclass
class loteria:
    size: str
    a: str
    b: str
    c: str

###### Helper Functions ######

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.route('/setup-tables')
@login_required
def setup():

    # Create table: users
    db.execute("CREATE TABLE IF NOT EXISTS users ( \
        id serial PRIMARY KEY NOT NULL, \
        username VARCHAR ( 255 ) UNIQUE NOT NULL, \
        password VARCHAR ( 255 ) NOT NULL, \
        created_on TIMESTAMP, \
        last_login TIMESTAMP \
        )")

    # Create table: parts
    db.execute("CREATE TABLE IF NOT EXISTS parts ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        color VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Create table: items
    db.execute("CREATE TABLE IF NOT EXISTS items ( \
        id serial PRIMARY KEY NOT NULL, \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        a_color VARCHAR ( 255 ), \
        b_color VARCHAR ( 255 ), \
        c_color VARCHAR ( 255 ), \
        status VARCHAR ( 255 ) \
        )")

    return "Setup Success!"


@app.route('/')
@login_required
def dashboard():


    # print(loteria)
    for key in loterias:
        # i = 0
        print(f"{key}:")
        tmp = loterias[key]
        print(tmp)
    items = db.execute("SELECT * FROM items")
    parts = db.execute("SELECT * FROM parts")
    user = db.execute("SELECT username from users WHERE id=:id", id=session["user_id"])
    return render_template('index.html', user=user, colors=colors, sizes=sizes, loterias=loterias)

@app.route('/items')
@login_required
def items():
    return render_template('items.html', loterias=loterias, colors=colors)

@app.route('/parts')
@login_required
def parts():
    return render_template('parts.html')

@app.route('/projections')
@login_required
def projections():
    return render_template('projections.html')

@app.route('/shipping')
@login_required
def shipping():
    return render_template('shipping.html')



###### ADMINSTRATIVE ######

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Serve registration page
    if request.method == 'GET':
        return render_template("register.html")

    # Process submitted form responses on POST
    else:

        # Error Checking
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", errcode=403, errmsg="Username required.")

        # Ensure password was submitted
        if not request.form.get("password"):
            return render_template("error.html", errcode=403, errmsg="Password required.")

        # Ensure password and password confirmation match
        if request.form.get("password") != request.form.get("passwordconfirm"):
            return render_template("error.html", errcode=403, errmsg="Passwords must match.")

        # Ensure minimum password length
        if len(request.form.get("password")) < 8:
            return render_template("error.html", errcode=403, errmsg="Password must be at least 8 characters.")

        # Store the hashed username and password
        username = request.form.get("username")
        hashedpass = generate_password_hash(request.form.get("password"))

        if username not in authusers:
            return render_template("error.html", errcode=403, errmsg="Unauthorized user.")

        # Check if username is already taken
        if not db.execute("SELECT username FROM users WHERE username LIKE (?)", username):

            # Add the username
            time = datetime.datetime.utcnow().isoformat()
            db.execute("INSERT INTO users (username, password, created_on) VALUES (:username, :hashedpass, :time)",
                        username=username, hashedpass=hashedpass, time=time)
            return redirect("/")

        else:
            return render_template("error.html", errcode=403, errmsg="Username invalid or already taken.")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", errcode=400, errmsg="Username required.")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("error.html", errcode=400, errmsg="Password required.")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists
        if len(rows) != 1:
            return render_template("register.html", errmsg="Username not found.")

        # Ensure username exists and password is correct
        if not check_password_hash(rows[0]["password"], request.form.get("password")):
            return render_template("error.html", errcode=403, errmsg="Incorrect password.")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Update "last_login"
        time = datetime.datetime.utcnow().isoformat()
        db.execute("UPDATE users SET last_login=:time WHERE id=:id", time=time, id=session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

   # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")




