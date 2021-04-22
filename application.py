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

###### DEFINITIONS ######
"""
item: fully assembled woodcut item
part: constituent piece that comprises an item, usually one of two or three
loteria: woodcut loteria pieces
"""

#TODO sort production queue by color sort by size
#TODO backs and boxes

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
authusers.append(os.getenv('USERC'))


###### TEMPLATES ######
# Set type variables
# Loteria
colors = ['black', 'red', 'turquoise', 'yellow', 'green', 'purple']
sizes = ['s', 'm', 'l']
loterias = {
    'La Dama': ['Frida', 'Frida Flowers', ],
    'La Sirena': ['Mermaid Body', 'Mermaid Hair', 'Mermaid Tail'],
    'La Mano': ['Hand', 'Hand Swirls', ],
    'La Bota': ['Boot', 'Boot Swirls', 'Boot Flames'],
    'El Corazon': ['Heart', 'Heart Swirls', ],
    'El Musico': ['Guitar', 'Guitar Hands', ],
    'La Estrella': ['Star', 'Star Swirls', ],
    'El Pulpo': ['Octopus', 'Octopus Swirls', 'Octopus Tentacles'],
    'La Rosa': ['Rose', 'Rose Swirls', 'Rose Leaves'],
    'La Calavera': ['Skull', 'Skull Flames', 'Skull Swirls'],
    'El Poder': ['Fist', 'Fist Swirls', 'Fist Wrist']
}

#TODO 86 this and the module it came from?
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


@app.route('/')
@login_required
def dashboard():

    print("--- LOADING ---")

    user = db.execute("SELECT username from users WHERE id=:id", id=session["user_id"])
    items = db.execute("SELECT * FROM items ORDER BY size ASC, name DESC")
    parts = db.execute("SELECT * FROM parts ORDER BY size ASC, name DESC, color ASC, qty DESC")

    # Query for production part totals
    totals = []
    for i in range(len(sizes)):
        totals.append([])
        for j in range(len(colors)):
            qty = db.execute("SELECT SUM(qty) FROM production WHERE size=:size AND color=:color", \
                                size=sizes[i], color=colors[j])
            if qty == 'None':
                qty = 0
            print(f"QTY======{qty}")
            totals[i].append(qty[0]['sum'])

        print(totals)

    # POPULATE production TABLE FROM PROJECTIONS

    # Identify current cycle
    cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")

    # Query for current cycle's projections
    projections = db.execute("SELECT * FROM projections WHERE cycle=:cycle", cycle=cycle[0]['id'])

    # Clear production table
    db.execute("DELETE FROM production")

    #

    # For each item in projections
    for item in projections:
        nombre = item['name']
        size = item['size']
        qty = item['qty']
        partcolor = []
        partcolor.append(item['a_color'])
        partcolor.append(item['b_color'])
        partcolor.append(item['c_color'])
        print(f"One {nombre} produces...")

        # Identify and capture from the item: each part's name and color
        for i in range(len(loterias[nombre])):
            name = loterias[nombre][i]
            color = partcolor[i]
            print(f"{color} {name}")

            # Query for qty of this part type already in production
            queued = db.execute("SELECT qty FROM production WHERE name=:name AND size=:size AND color=:color",
                                name=name, size=size, color=color)
            print(f"queued:{queued}")

            # Identify number of that parts already on hand
            onhand = db.execute("SELECT qty FROM parts WHERE name=:name AND size=:size AND color=:color", 
                                name=name, size=size, color=color)           
            print(f"onhand:{onhand}")

            # If there is an onhand quantity, subtract that from the projection qty to yield production qty
            if onhand:
                qty = qty - onhand[0]['qty']

            # Create new production entry for this type if none exists already
            if not queued:
                db.execute("INSERT INTO production (name, size, color, qty) VALUES (:name, :size, :color, :qty)", 
                                name=name, size=size, color=color, qty=qty)

            # Else update existing quantity
            else:
                db.execute("UPDATE production SET qty=:qty WHERE name=:name AND size=:size AND color=:color", 
                                qty=qty, name=name, size=size, color=color)
        print()

    production = db.execute("SELECT * FROM production ORDER BY qty DESC, size ASC")
    time = datetime.datetime.utcnow().isoformat()
    print(cycle)
    print(items)
    return render_template('index.html', production=production, loterias=loterias, sizes=sizes, \
        colors=colors, user=user, items=items, parts=parts, projections=projections, totals=totals, cycle=cycle, time=time)


@app.route('/parts', methods=['GET', 'POST'])
@login_required
def parts():
    if request.method == 'GET':
        parts = db.execute("SELECT * FROM parts WHERE qty>0 ORDER BY size ASC, name DESC, color DESC, qty DESC")
        return render_template('parts.html', parts=parts, loterias=loterias, sizes=sizes, colors=colors)

    # Upon POSTing form submission
    else:
        part = request.form.get("part")
        size = request.form.get("size")
        color = request.form.get("color")
        qty = int(request.form.get("qty"))
        print(part, size, color, qty)

        # What quantity of this part already exists?
        onhand = db.execute("SELECT qty FROM parts WHERE \
                            name=:name AND size=:size AND color=:color", \
                            name=part, size=size, color=color)
        print(f"Fetching onhand ...")
        print(onhand)

        # None, create new entry
        if not onhand:
            db.execute("INSERT INTO parts (name, size, color, qty) VALUES \
                        (:name, :size, :color, :qty)", \
                        name=part, size=size, color=color, qty=qty)
            print("New parts entry created.")                        

        # Update existing entry's quantity
        else:
            updated = onhand[0]['qty'] + qty
            db.execute("UPDATE parts SET qty=:updated WHERE \
                        name=:name AND size=:size AND color=:color", \
                        updated=updated, name=part, size=size, color=color)
            print("Existing parts inventory quantity updated.")                        

        return redirect('/parts')


@app.route('/items', methods=['GET', 'POST'])
@login_required
def items():
    if request.method == 'GET':
        items = db.execute("SELECT * FROM items ORDER BY size ASC, name DESC")
        return render_template('items.html', items=items, loterias=loterias, sizes=sizes, colors=colors)

    # Upon POSTing form submission
    else:
        item = request.form.get("item")
        size = request.form.get("size")
        a = request.form.get("Color A")
        b = request.form.get("Color B")
        c = request.form.get("Color C")
        qty = int(request.form.get("qty"))
        print(qty, item, size, a, b, c)

        for i in range(qty):

            db.execute("INSERT INTO items (name, size, a_color, b_color, c_color) VALUES \
                     (:item, :size, :a_color, :b_color, :c_color)", item=item, size=size, a_color=a, b_color=b, c_color=c)

        #TODO remove from parts when making item

        return redirect('/items')


@app.route('/projections', methods=['GET', 'POST'])
@login_required
def projections():
    if request.method == 'GET':

        # Check for "current" cycle
        active = db.execute("SELECT id, name, created_on FROM cycles WHERE current='TRUE'")
        current = active
        print(f"current:{current}")

        # Set newest cycle as "current" when there is none
        if not active:
            newest = db.execute("SELECT id FROM cycles ORDER BY id DESC LIMIT 1")
            db.execute("UPDATE cycles SET current='true' WHERE id=:active", active=newest[0]['id'])

        # Capture id of active "current" cycle
        else:
            active = active[0]['id']
        print(f"active:{active}")

        # List all available non-current cycles
        cycles = db.execute("SELECT id, name, created_on FROM cycles WHERE current='FALSE'")
        print(f"cycles:{cycles}")

        # Select projections from current cycle only
        projections = db.execute("SELECT * FROM projections WHERE cycle=:active ORDER BY size ASC, name DESC, qty DESC", active=active)
        return render_template('projections.html', projections=projections, current=current, cycles=cycles, loterias=loterias, sizes=sizes, colors=colors)

    # Upon POSTing form submission
    else:
        item = request.form.get("item")
        size = request.form.get("size")
        a = request.form.get("Color A")
        b = request.form.get("Color B")
        c = request.form.get("Color C")
        qty = int(request.form.get("qty"))

        # Identify current cycle
        active = db.execute("SELECT id, name, created_on FROM cycles WHERE current='TRUE'")
        print(f"active cycle:{active}")
        cycle = active[0]['id']

        # What quantity of this item is already in projections?
        projected = db.execute("SELECT qty FROM projections WHERE \
                            name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color \
                            AND cycle=:cycle", \
                            name=item, size=size, a_color=a, b_color=b, c_color=c, cycle=cycle)
        print(f"Fetching projected ...")
        print(projected)

        # None, create new entry
        if not projected:
            db.execute("INSERT INTO projections (name, size, a_color, b_color, c_color, qty, cycle) VALUES \
                        (:name, :size, :a_color, :b_color, :c_color, :qty, :cycle)", \
                        name=item, size=size, a_color=a, b_color=b, c_color=c, qty=qty, cycle=cycle)
            print("New projection created.")                        

        # Update existing entry's quantity
        else:
            updated = projected[0]['qty'] + qty
            db.execute("UPDATE projections SET qty=:updated WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color \
                        AND cycle=:cycle", \
                        updated=updated, name=item, size=size, a_color=a, b_color=b, c_color=c)
            print("Existing projection updated.")                        

        return redirect('/projections')


@app.route('/cycle', methods=['GET', 'POST'])
@login_required
def cycle():

    #TODO cycle management. feature: delete a cycle
    if request.method == 'GET':
        return render_template("cycle.html")
    
    # Upon POSTed submission
    else:
        print("/cycle: POST")
        name = request.form.get("name")

        # Make all other cycles not current
        db.execute("UPDATE cycles SET current='FALSE'")

        # Change current cycle selection
        if not name:
            cycle_id = request.form.get("cycle")
            print(f"cycle:{cycle_id}")
            db.execute("UPDATE cycles SET current='TRUE' WHERE id=:id", id=cycle_id)

        # Make a new name
        else:
            # Create new Cycle
            time = datetime.datetime.utcnow().isoformat()
            db.execute("INSERT INTO cycles (name, created_on, current) VALUES (:name, :time, 'TRUE')", name=name, time=time)

        return redirect('/projections')

@app.route('/shipping')
@login_required
def shipping():
    return render_template('shipping.html')


###### SETUP ######

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

    # Create table: projections
    db.execute("CREATE TABLE IF NOT EXISTS projections ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        a_color VARCHAR ( 255 ), \
        b_color VARCHAR ( 255 ), \
        c_color VARCHAR ( 255 ), \
        qty INTEGER, \
        cycle INTEGER \
        )")
    
    # Create table: production
    db.execute("CREATE TABLE IF NOT EXISTS production ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        color VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Create table: cycles
    db.execute("CREATE TABLE IF NOT EXISTS cycles ( \
        id serial PRIMARY KEY NOT NULL, \
        name VARCHAR (255), \
        created_on TIMESTAMP, \
        current BOOL \
        )")
    
    # If empty cycles table
    data = db.execute("SELECT * FROM cycles")
    if not data:
        # Seed table with test cycle
        time = datetime.datetime.utcnow().isoformat()
        db.execute("INSERT INTO cycles (name, created_on, current) VALUES ('test cycle', :time, 'TRUE')", time=time)

    #Create table: summary
    db.execute("CREATE TABLE IF NOT EXISTS summary ()")


    return "Setup Success!"


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




