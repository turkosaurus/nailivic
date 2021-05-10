import os
import requests
import urllib.parse
import datetime
import csv

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
#TODO treat backs like a part

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

#TODO draw all this from a a database instead
colors = ['black', 'red', 'turquoise', 'yellow', 'green', 'purple', 'nekkid']
sizes = ['s', 'm', 'l']
loterias = {
    'La Dama': ['Frida', 'Frida Flowers', 'Frida Backs'],
    'La Sirena': ['Mermaid Body', 'Mermaid Hair', 'Mermaid Tail', 'Mermaid Backs'],
    'La Mano': ['Hand', 'Hand Swirls', 'Hand Backs'],
    'La Bota': ['Boot', 'Boot Swirls', 'Boot Flames', 'Boot Backs'],
    'El Corazon': ['Heart', 'Heart Swirls', 'Heart Backs'],
    'El Musico': ['Guitar', 'Guitar Hands', 'Guitar Backs'],
    'La Estrella': ['Star', 'Star Swirls', 'Star Backs'],
    'El Pulpo': ['Octopus', 'Octopus Swirls', 'Octopus Tentacles', 'Octopus Backs'],
    'La Rosa': ['Rose', 'Rose Swirls', 'Rose Leaves', 'Rose Backs'],
    'La Calavera': ['Skull', 'Skull Flames', 'Skull Swirls', 'Skull Backs'],
    'El Poder': ['Fist', 'Fist Swirls', 'Fist Wrist', 'Fist Backs']
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


@app.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():

    if request.method == 'GET':
        print("--- LOADING ---")

        # Identify current cycle
        cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")

        # Query for data
        user = db.execute("SELECT username from users WHERE id=:id", id=session["user_id"])
        items = db.execute("SELECT * FROM items ORDER BY size ASC, name DESC")
        parts = db.execute("SELECT * FROM parts ORDER BY size ASC, name DESC, color ASC, qty DESC")

        # Query for production part totals
        totals = []

        # For each size
        for i in range(len(sizes)):

            # Make a list to hold the color totoals
            totals.append([])

            # For each color
            for j in range(len(colors)):
                qty = db.execute("SELECT SUM(qty) FROM production WHERE size=:size AND color=:color", \
                                    size=sizes[i], color=colors[j])
                print(f'qty:{qty} for {sizes[i]}, {colors[j]}')
                if qty[0]['sum'] == None:
                    qty[0]['sum'] = ''
                print(f"qty {qty}")
                totals[i].append(qty[0]['sum'])

            print(totals)

        #TODO backs
        backs = '#TODO'

        # Box Production Total
        box_prod = db.execute("SELECT SUM(qty_prod) FROM boxes")
        box_prod = box_prod[0]['sum']

        # Box Inventory Itemized
        boxes = db.execute("SELECT * FROM boxes")

        production = db.execute("SELECT * FROM production ORDER BY qty DESC, size ASC")
        time = datetime.datetime.utcnow().isoformat()
        print(cycle)
        print(items)
        return render_template('index.html', production=production, boxes=boxes, box_prod=box_prod, backs=backs, loterias=loterias, sizes=sizes, \
            colors=colors, user=user, items=items, parts=parts, projections=projections, totals=totals, cycle=cycle, time=time)

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

        return redirect('/')


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

        newloterias = db.execute("SELECT nombre FROM loterias")
        print(newloterias)

        # Select projections from current cycle only
        projections = db.execute("SELECT * FROM projections WHERE cycle=:active ORDER BY size ASC, name DESC, qty DESC", active=active)
        return render_template('projections.html', projections=projections, current=current, cycles=cycles, loterias=newloterias, sizes=sizes, colors=colors)

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


@app.route('/production', methods=['GET'])
@login_required
def production():
    # (RE)BUILD PRODUCTION TABLE

    # Identify current cycle
    cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")

    # Query for current cycle's projections
    projections = db.execute("SELECT * FROM projections WHERE cycle=:cycle", cycle=cycle[0]['id'])

    # Clear all production data
    db.execute("DELETE FROM production")
    db.execute("UPDATE boxes SET qty_prod=0")

    # Rebuild production table
    for item in projections:
        nombre = item['name']
        size = item['size']
        qty = item['qty']
        partcolor = []
        partcolor.append(item['a_color'])
        partcolor.append(item['b_color'])
        partcolor.append(item['c_color'])
        print(f"One {nombre} produces...")


        # Adjust box production
        # Add boxes to production if small
        if size == sizes[0]:
            boxname = loterias[nombre][0]
            print(f'boxname={boxname}')
            boxes = db.execute("SELECT * FROM boxes WHERE name=:name", name=boxname)

            # Add new box producion entry with production quantity
            if not boxes:
                db.execute("INSERT INTO boxes (name, qty_prod) VALUES (:name, :qty_prod)", name=boxname, qty_prod=qty)

            # Update existing box entry with new production quantity
            else:
                # Handle bug when subtracting nonetype
                if boxes[0]['qty_onhand'] is None:
                    boxes[0]['qty_onhand'] = 0                
                box_qty_prod = qty - boxes[0]['qty_onhand']

                # Update box production quantities
                db.execute("UPDATE boxes SET qty_prod=:box_qty_prod WHERE name=:name", box_qty_prod=box_qty_prod, name=boxname)



        # Query for quantity of projected items that are already on hand 
        items_onhand = db.execute("SELECT COUNT(id) FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color",
                        name=nombre, size=size, a_color=partcolor[0], b_color=partcolor[1], c_color=partcolor[2])
        items_onhand = items_onhand[0]['count']
        
        # Subtract on hand items from projected items
        qty = qty - items_onhand

        # If production still necessary becuase demand exceeds onhand, process the requirements
        if qty > 0:

            # Identify and capture from each item: each part's name and color
            for i in range(len(loterias[nombre])):
                name = loterias[nombre][i]
                color = partcolor[i]
                print(f"{color} {name}")

                # Query for qty of this part type already in production
                queued = db.execute("SELECT qty FROM production WHERE name=:name AND size=:size AND color=:color",
                                    name=name, size=size, color=color)
                print(f"queued:{queued}")

                # Identify number of that parts already on hand
                parts_onhand = db.execute("SELECT qty FROM parts WHERE name=:name AND size=:size AND color=:color", 
                                    name=name, size=size, color=color)           
                print(f"parts_onhand:{parts_onhand}")

                # If there are parts on hand, subtract tham from the projection qty to yield production qty
                if parts_onhand:
                    qty = qty - parts_onhand[0]['qty']

                # Create new production entry for this type if none exists already
                if not queued:
                    db.execute("INSERT INTO production (name, size, color, qty) VALUES (:name, :size, :color, :qty)", 
                                    name=name, size=size, color=color, qty=qty)

                # Else update existing quantity
                else:
                    db.execute("UPDATE production SET qty=:qty WHERE name=:name AND size=:size AND color=:color", 
                                    qty=qty, name=name, size=size, color=color)
        print()

    return redirect("/projections")


@app.route('/box', methods=['GET', 'POST'])
@login_required
def box():
    if request.method == 'GET':
        return "#TODO"
    else:
        # Make a box
        name = request.form.get("box")
        qty = request.form.get("boxqty")

        # Fetch and update current quantity of boxes onhand and in production queue
        boxes = db.execute("SELECT * FROM boxes WHERE name=:name", name=name)
        print(boxes)
        if boxes:
            qty_onhand = boxes[0]['qty_onhand'] + qty

            #TODO handle negatives
            # Update production quantity
            qty_prod = boxes[0]['qty_prod'] - qty
            db.execute("UPDATE boxes SET qty_onhand=:qty_onhand, qty_prod=:qty_prod WHERE name=:name", qty_onhand=qty_onhand, qty_prod=qty_prod, name=name)
            #TODO update productions

        if not boxes:
            db.execute("INSERT INTO boxes (name, qty_onhand) VALUES (:name, :qty_onhand)", name=name, qty_onhand=qty)

        return redirect('/')


@app.route('/shipping')
@login_required
def shipping():
    return render_template('shipping.html')


###### SETUP ######
@app.route('/admin', methods=['GET'])
@login_required
def admin():
    cycles = db.execute("SELECT * FROM cycles")
    return render_template('admin.html', cycles=cycles)


@app.route('/admin/<path>', methods=['GET', 'POST'])
@login_required
def config(path):

        # Change or make new cycle
        if path == 'cycle':

            print("Making a new cycle.")
            name = request.form.get("name")

            # Make all other cycles not current

            # Change current cycle selection
            if not name:
                cycle_id = request.form.get("cycle")
                print(f"cycle:{cycle_id}")

                # Change active cycle
                db.execute("UPDATE cycles SET current='FALSE'")
                db.execute("UPDATE cycles SET current='TRUE' WHERE id=:id", id=cycle_id)

            # Make a new cycle
            else:
                # Create new Cycle
                db.execute("UPDATE cycles SET current='FALSE'")
                time = datetime.datetime.utcnow().isoformat()
                db.execute("INSERT INTO cycles (name, created_on, current) VALUES (:name, :time, 'TRUE')", name=name, time=time)

            return redirect('/projections')


        # Delete a Cycle
        if path == 'delete':
            name = request.form.get("delname")
            print(name)
            if name != 'test cycle':
                db.execute("DELETE from CYCLES where name=:name", name=name)
                db.execute("UPDATE cycles SET current='TRUE' WHERE id=1")
                return render_template("message.html", errmsg="Successfully deleted cycle.")
            else:
                return render_template("error.html", errcode="403", errmsg="Test cycle may not be deleted.")

        # Setup tables
        if path == 'setup-tables':
            # Create table: users
            db.execute("CREATE TABLE IF NOT EXISTS users ( \
                id serial PRIMARY KEY NOT NULL, \
                username VARCHAR ( 255 ) UNIQUE NOT NULL, \
                password VARCHAR ( 255 ) NOT NULL, \
                created_on TIMESTAMP, \
                last_login TIMESTAMP \
                )")

            # Create table: parts
            # db.execute("DROP TABLE parts")
            db.execute("CREATE TABLE IF NOT EXISTS parts ( \
                name VARCHAR ( 255 ) NOT NULL, \
                size VARCHAR ( 255 ) NOT NULL, \
                color VARCHAR ( 255 ), \
                qty INTEGER \
                )")

            # Create table: items
            # db.execute("DROP TABLE items")
            db.execute("CREATE TABLE IF NOT EXISTS items ( \
                id serial PRIMARY KEY NOT NULL, \
                name VARCHAR ( 255 ) NOT NULL, \
                size VARCHAR ( 255 ) NOT NULL, \
                a_color VARCHAR ( 255 ), \
                b_color VARCHAR ( 255 ), \
                c_color VARCHAR ( 255 ), \
                status VARCHAR ( 255 ) \
                )")

            # Create table: boxes
            # db.execute("DROP TABLE boxes")
            db.execute("CREATE TABLE IF NOT EXISTS boxes ( \
                name VARCHAR ( 255 ), \
                qty_onhand INTEGER, \
                qty_prod INTEGER \
                )")
            
            # Create table: projections
            # db.execute("DROP TABLE projections")
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
            # db.execute("DROP TABLE production")
            db.execute("CREATE TABLE IF NOT EXISTS production ( \
                name VARCHAR ( 255 ) NOT NULL, \
                size VARCHAR ( 255 ) NOT NULL, \
                color VARCHAR ( 255 ), \
                qty INTEGER \
                )")

            # Create table: cycles
            # db.execute("DROP TABLE cycles")
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
            db.execute("DROP TABLE summary")
            db.execute("CREATE TABLE IF NOT EXISTS summary ()")


            return render_template('message.html', errmsg="Success, tables now setup.")


        # Setup loterias
        if path == 'setup-loterias':

            # Read loterias.csv into a SQL table
            with open('loterias.csv', 'r') as csvfile:

                print('Reading loterias.csv...')
                csv_reader = csv.reader(csvfile)

                db.execute("CREATE TABLE IF NOT EXISTS loterias ( \
                    nombre VARCHAR (255) NOT NULL, \
                    a VARCHAR (255), \
                    b VARCHAR (255), \
                    c VARCHAR (255), \
                    backs VARCHAR (255) \
                    )")

                db.execute("DELETE from loterias")

                for row in csv_reader:
                    db.execute("INSERT INTO loterias (nombre, a, b, c, backs) VALUES (:nombre, :a, :b, :c, :backs)", \
                                    nombre=row[0], a=row[1], b=row[2], c=row[3], backs=row[4])

            return render_template('message.html', errmsg="Success, new cycle created")




        # Not a valid admin route
        else:
            return redirect('/')



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




