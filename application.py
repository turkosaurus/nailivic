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
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

###### DEFINITIONS ######
"""
item: fully assembled woodcut item
part: constituent piece that comprises an item, usually one of two or three
loteria: woodcut loteria pieces
"""


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

colors = ['🖤 black', '❤️ red', '💙 turq.', '💛 yellow', '💚 green', '💜 purple']
# colors = ['black', 'red', 'turquoise', 'yellow', 'green', 'purple']
sizes = ['s', 'm', 'l']


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


###### QUEUE ######
# These functions produce production table, calculating projecitons less inventory
# Negative values can dequeue items

# Queue part(s) of specified color for production
def queuepart(name, size, color, qty):
    print("queuepart()")

    # Identify how many parts of that type are already on hand
    parts_onhand = db.execute("SELECT qty FROM parts WHERE name=:name AND size=:size AND color=:color", 
                        name=name, size=size, color=color)
    print(f"{parts_onhand} {size} {color} {name} in inventory.")

    # Subtract parts on hand from demand qty
    if parts_onhand:
        qty = qty - parts_onhand[0]['qty']

    # Identify how many parts of that type are already in production
    parts_inprod = db.execute("SELECT qty FROM production where name=:name AND size=:size AND color=:color", 
                        name=name, size=size, color=color)
    print(f"{parts_inprod} {size} {color} {name} already in production.")
    
    # Entry already exists in production queue
    if parts_inprod:

        # Add parts qty already in prod to parts demand to reach updated prod qty
        qty = qty + parts_inprod[0]['qty']

        # Update existing production queue entry
        db.execute("UPDATE production SET qty=:qty WHERE name=:name AND size=:size AND color=:color", 
                    name=name, size=size, color=color, qty=qty)
        print(f"{size} {color} {name} production qty of {parts_inprod[0]['qty']} increased to {qty}")

    # Add new production queue entry
    else:
        db.execute("INSERT INTO production (name, size, color, qty) VALUES (:name, :size, :color, :qty)", 
                    name=name, size=size, color=color, qty=qty)
        print(f"{qty} {size} {color} {name} inserted into production queue")


# Queue backs for production            
def queuebacks(name, size, qty):
    print("queuebacks()")
    
    # Identify how many parts of that type are already on hand
    parts_onhand = db.execute("SELECT qty FROM parts WHERE name=:name AND size=:size", 
                        name=name, size=size)
    print(f"{parts_onhand} {size} {name} in inventory.")

    # Subtract parts on hand from demand qty
    if parts_onhand:
        qty = qty - parts_onhand[0]['qty']

    # Identify how many parts of that type are already in production
    parts_inprod = db.execute("SELECT qty FROM production where name=:name AND size=:size", 
                        name=name, size=size)
    print(f"{parts_inprod} {size} {name} already in production.")


    # Entry already exists in production queue
    if parts_inprod:

        # Add parts qty already in prod to parts demand to reach updated prod qty
        qty = qty + parts_inprod[0]['qty']

        # Update existing production queue entry
        db.execute("UPDATE production SET qty=:qty WHERE name=:name AND size=:size", 
                    name=name, size=size, qty=qty)
        print(f"{size} {name} production qty of {parts_inprod[0]['qty']} increased to {qty}")

    # Add new production queue entry
    else:
        db.execute("INSERT INTO production (name, size, qty) VALUES (:name, :size, :qty)", 
                    name=name, size=size, qty=qty)
        print(f"{qty} {size} {name} inserted into production queue")
      

# Queue boxes for production
def queueboxes(name, qty):
    print("queueboxes()")

    # Identify how many boxes of that type are already on hand
    boxes_onhand = db.execute("SELECT * FROM boxes WHERE name=:name", name=name)
    print(f"{boxes_onhand} {name} boxes in inventory")

    if boxes_onhand:
        qty = qty - boxes_onhand[0]['qty']

    # Identify how many boxes of that type are already queued for production
    boxes_inprod = db.execute("SELECT * FROM boxprod WHERE name=:name", name=name)
    print(f"{boxes_inprod} {name} boxes already in production")

    # Entry already exists in boxprod
    if boxes_inprod:
        qty = qty + boxes_inprod[0]['qty']
        db.execute("UPDATE boxprod SET qty=:qty WHERE name=:name", qty=qty, name=name)
        print(f"{name} boxes production queue of {boxes_inprod[0]['qty']} increased to {qty}")

    # Make new entry in boxprod
    else:
        db.execute("INSERT INTO boxprod (name, qty) VALUES (:name, :qty)", name=name, qty=qty)
        print(f"{qty} {name} boxes in production queue")


# (RE)BUILD PRODUCTION TABLE
def makequeue():

    # Identify current cycle
    cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")

    # Query for current cycle's projections
    projections = db.execute("SELECT * FROM projections WHERE cycle=:cycle", cycle=cycle[0]['id'])

    # Clear all production data
    db.execute("DELETE FROM production")
    db.execute("UPDATE boxprod SET qty=0")

    newloterias = db.execute("SELECT * FROM loterias")

    # Ensure that every item in projections is added to the production queue (less inventory on hand)
    for item in projections:
        nombre = item['name']
        size = item['size']
        qty = item['qty']
        a = item['a_color']
        b = item['b_color']
        c = item['c_color']
        print(f"{qty} {size} {nombre} {a} {b} {c} produces...")

        # Queue box for production of small items
        if size == sizes[0]:
            queueboxes(nombre, qty)
        
        # Identify how many items of that type, size, colors exist in inventory

        # 3 color item
        if c is not None:
            items_onhand = db.execute("SELECT COUNT(id) FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color",
                                        name=nombre, size=size, a_color=a, b_color=b, c_color=c)
 
        # 2 color item
        else:
            items_onhand = db.execute("SELECT COUNT(id) FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color",
                                        name=nombre, size=size, a_color=a, b_color=b)

        print(items_onhand)
        print(f"Counting {items_onhand[0]['count']} {size} {nombre} {a} {b} {c} in inventory.")
        items_onhand = items_onhand[0]['count']
        
        # Calculate items needed for production; subtract inventory items from projections['qty']
        qty = qty - items_onhand

       # Check for need to add parts to production queue
        if qty > 0:

            # Translate nombre to name
            names = db.execute("SELECT * FROM loterias WHERE nombre=:nombre", nombre=nombre)

            # Update parts production queue

            # a_color
            name = names[0]['a']
            queuepart(name, size, a, qty)

            # b_color
            name = names[0]['b']
            queuepart(name, size, b, qty)

            # c_color
            if c is not None:
                name = names[0]['c']
                queuepart(name, size, c, qty)

            # backs
            name = names[0]['backs']
            queuebacks(name, size, qty)

    # (RE)BUILD PRODUCTION SUMMARY TOTALS
        # TODO calculate and return



###### MAIN ROUTES ######
@app.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():

    if request.method == 'GET':
        print("--- LOADING ---")

        # Query for relevant data
        cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")
        if not cycle:
            db.execute("UPDATE cycles SET current='TRUE' WHERE name='test cycle'")
            cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")
        user = db.execute("SELECT username from users WHERE id=:id", id=session["user_id"])
        items = db.execute("SELECT * FROM items ORDER BY size ASC, name DESC")
        parts = db.execute("SELECT * FROM parts ORDER BY size ASC, name DESC, color ASC, qty DESC")
        newloterias = db.execute("SELECT * FROM loterias")

        # Sum totals for each color & size
        totals = []
        ## For each size
        for i in range(len(sizes)):

            # Make a list to hold the color totoals
            totals.append([])

            # For each color within the size, sum the number of parts
            for j in range(len(colors)):
                qty = db.execute("SELECT SUM(qty) FROM production WHERE size=:size AND color=:color", \
                                    size=sizes[i], color=colors[j])
                print(f'qty:{qty} for {sizes[i]}, {colors[j]}')
                # Sanitize "None" into ''
                if qty[0]['sum'] == None:
                    qty[0]['sum'] = ''
                print(f"qty {qty}")

                # Append current color's totals to the current size's list
                totals[i].append(qty[0]['sum'])

            # Tally backs in production
            backs = db.execute("SELECT SUM(qty) FROM production WHERE size=:size AND name IN (SELECT backs FROM loterias)", size=sizes[i])
            # Sanitize "None" into ''
            if backs[0]['sum'] == None:
                backs[0]['sum'] = ''
            totals[i].append(backs[0]['sum'])

            print(totals)

        # Box Production Total
        box_prod_total = db.execute("SELECT SUM(qty) FROM boxprod")
        box_prod_total = box_prod_total[0]['sum']

        # Box Inventory & Production
        boxes = db.execute("SELECT * FROM boxes WHERE qty>0")
        boxprod = db.execute("SELECT * FROM boxprod WHERE qty>0")

        production = db.execute("SELECT * FROM production ORDER BY qty DESC, size ASC")
        time = datetime.datetime.utcnow().isoformat()
        print(cycle)
        print(items)
        print(newloterias)
        return render_template('index.html', production=production, boxes=boxes, boxprod=boxprod, box_prod_total=box_prod_total, backs=backs, loterias=newloterias, sizes=sizes, \
            colors=colors, user=user, items=items, parts=parts, projections=projections, totals=totals, cycle=cycle, time=time)

    # Upon POSTing form submission
    else:
        part = request.form.get("part")
        size = request.form.get("size")
        color = request.form.get("color")
        qty = int(request.form.get("qty"))
        print(part, size, color, qty)

        if not size:
            return render_template('error.html', errcode='403', errmsg='Size must be specified for part')

        # Determine if part with color, or backs
        backs_onhand = db.execute("SELECT backs FROM loterias WHERE backs=:part", part=part)

        # BACKS
        if backs_onhand:
            print(f"Backs on hand: {backs_onhand}")

            # What quantity of this part already exists?
            onhand = db.execute("SELECT qty FROM parts WHERE \
                                name=:name AND size=:size", \
                                name=part, size=size)

            print(f"Fetching onhand backs...")
            print(onhand)

            # None, create new entry
            if not onhand:
                db.execute("INSERT INTO parts (name, size, qty) VALUES \
                            (:name, :size, :qty)", \
                            name=part, size=size, qty=qty)
                print(f"New {size} {part} entry created with qty {qty}.")                        

            # Update existing entry's quantity
            else:
                new_qty = onhand[0]['qty'] + qty
                db.execute("UPDATE parts SET qty=:qty WHERE \
                            name=:name AND size=:size", qty=new_qty, name=part, size=size)
                print(f"Existing {size} {part} inventory quantity updated from {onhand[0]['qty']} to {new_qty}.")                        

            # Update production queue
        
            # Identify matching part that is already in production
            parts_inprod = db.execute("SELECT qty FROM production WHERE \
                            name=:name AND size=:size", name=part, size=size)

            if parts_inprod:

                # Subtract parts being made from production queue
                new_partsprod = parts_inprod[0]['qty'] - qty

                # Remove entry because <0
                if new_partsprod < 1:
                    db.execute("DELETE FROM production WHERE \
                            name=:name AND size=:size", name=part, size=size)

                # Update entry to new depleted quantity after accouting for newly produced parts
                else:
                    db.execute("UPDATE production SET qty=:new_partsprod WHERE \
                            name=:name AND size=:size", name=part, size=size, new_partsprod=new_partsprod)

        # PARTS WITH COLORS
        else:
            # What quantity of this part already exists?
            onhand = db.execute("SELECT qty FROM parts WHERE \
                                name=:name AND size=:size AND color=:color", \
                                name=part, size=size, color=color)

            print(f"Fetching onhand parts...")
            print(onhand)

            #BUG this is creating duplicates for backs
            # None, create new entry
            if not onhand:
                db.execute("INSERT INTO parts (name, size, color, qty) VALUES \
                            (:name, :size, :color, :qty)", \
                            name=part, size=size, color=color, qty=qty)
                print(f"New {size} {color} {part} entry created with qty {qty}.")                        

            # Update existing entry's quantity
            else:
                new_qty = onhand[0]['qty'] + qty
                db.execute("UPDATE parts SET qty=:qty WHERE \
                            name=:name AND size=:size AND color=:color", qty=new_qty, name=part, size=size, color=color)
                print(f"Existing {size} {color} {part} inventory quantity updated from {onhand[0]['qty']} to {new_qty}.")                        

            # Update production queue
        
            # Identify matching part that is already in production
            parts_inprod = db.execute("SELECT qty FROM production WHERE \
                            name=:name AND size=:size AND color=:color", name=part, size=size, color=color)

            if parts_inprod:

                # Subtract parts being made from production queue
                new_partsprod = parts_inprod[0]['qty'] - qty

                # Remove entry because <0
                if new_partsprod < 1:
                    db.execute("DELETE FROM production WHERE \
                            name=:name AND size=:size AND color=:color", name=part, size=size, color=color)

                # Update entry to new depleted quantity after accouting for newly produced parts
                else:
                    db.execute("UPDATE production SET qty=:new_partsprod WHERE \
                            name=:name AND size=:size AND color=:color", name=part, size=size, color=color, new_partsprod=new_partsprod)

        return redirect('/')


@app.route('/items', methods=['GET', 'POST'])
@login_required
def items():
    if request.method == 'GET':
        items = db.execute("SELECT * FROM items ORDER BY size ASC, name DESC")
        newloterias = db.execute("SELECT nombre FROM loterias")
        print(newloterias)
        return render_template('items.html', items=items, loterias=newloterias, sizes=sizes, colors=colors)

    # Upon POSTing form submission
    else:
        item = request.form.get("item")
        size = request.form.get("size")
        a = request.form.get("Color A")
        b = request.form.get("Color B")
        c = request.form.get("Color C")
        qty = int(request.form.get("qty"))
        print("POST form with values:")
        print(qty, item, size, a, b, c)

        ## Validation
        # Return error if missing basic entries
        if (size is None) or (a is None) or (b is None):
            return render_template('error.html', errcode='403', errmsg='Invalid entry. All Items must have a size and at least 2 colors.')

        # Test for appropriateness of c_color presence
        ctest = db.execute("SELECT c FROM loterias WHERE nombre=:name", name=item)

        # No c is given
        if not c:
            # But there should be a c
            if ctest[0]['c'] != '':
                return render_template('error.html', errcode='403', errmsg='Invalid entry. Required color missing.')

        # Superfulous c value is given
        else:
            if ctest[0]['c'] == '':
                return render_template('error.html', errcode='403', errmsg='Invalid entry. Too many colors selected.')

        # Validation complete. Now remove from parts and add to items.

        # Deplete parts inventory
        # Find parts names using item name
        names = db.execute("SELECT * FROM loterias WHERE nombre=:item", item=item)

        # Deplete backs
        # Update inventory
        backs_onhand = db.execute("SELECT qty FROM parts WHERE name=:backs AND size=:size", backs=names[0]['backs'], size=size)
        if backs_onhand:
            print(f'backs_onhand:{backs_onhand}')
            new_qty = backs_onhand[0]['qty'] - qty

            # Remove entry if update would be cause qty to be less than 1
            if new_qty < 1:
                db.execute("DELETE FROM parts WHERE name=:backs AND size=:size", backs=names[0]['backs'], size=size)

            # Update existing entry
            else:
                db.execute("UPDATE parts SET qty=:qty WHERE name=:backs AND size=:size", qty=new_qty, backs=names[0]['backs'], size=size)

            queuebacks(names[0]['backs'], size, qty * -1)

        #Deplete a
        # Update inventory
        a_onhand = db.execute("SELECT qty FROM parts WHERE name=:name AND size=:size AND color=:color", name=names[0]['a'], size=size, color=a)
        if a_onhand:
            new_qty = a_onhand[0]['qty'] - qty

            # Remove entry if update would be cause qty to be less than 1
            if new_qty < 1:
                db.execute("DELETE FROM parts WHERE name=:name AND size=:size AND color=:color", name=names[0]['a'], size=size, color=a)

            # Update existing entry
            else:
                db.execute("UPDATE parts SET qty=:qty WHERE name=:name AND size=:size AND color=:color", qty=new_qty, name=names[0]['a'], size=size, color=a)

            # Update production
            queuepart(names[0]['a'], size, a, qty * -1)

        #Deplete b
        # Update inventory
        b_onhand = db.execute("SELECT qty FROM parts WHERE name=:name AND size=:size AND color=:color", name=names[0]['b'], size=size, color=b)
        if b_onhand:
            new_qty = b_onhand[0]['qty'] - qty

            # Remove entry if update would be cause qty to be less than 1
            if new_qty < 1:
                db.execute("DELETE FROM parts WHERE name=:name AND size=:size AND color=:color", name=names[0]['b'], size=size, color=b)

            # Update existing entry
            else:
                db.execute("UPDATE parts SET qty=:qty WHERE name=:name AND size=:size AND color=:color", qty=new_qty, name=names[0]['b'], size=size, color=b)

            # Update production
            queuepart(names[0]['b'], size, b, qty * -1)

        #Deplete c
        if c is not None:
            # Update inventory
            c_onhand = db.execute("SELECT qty FROM parts WHERE name=:name AND size=:size AND color=:color", name=names[0]['c'], size=size, color=c)
            if c_onhand:
                new_qty = c_onhand[0]['qty'] - qty

                # Remove entry if update would be cause qty to be less than 1
                if new_qty < 1:
                    db.execute("DELETE FROM parts WHERE name=:name AND size=:size AND color=:color", name=names[0]['c'], size=size, color=c)

                # Update existing entry
                else:
                    db.execute("UPDATE parts SET qty=:qty WHERE name=:name AND size=:size AND color=:color", qty=new_qty, name=names[0]['c'], size=size, color=c)

                # Update production
                queuepart(names[0]['c'], size, c, qty * -1)


        # Make new item(s)
        for i in range(qty):

            # Insert an item for every item made
            db.execute("INSERT INTO items (name, size, a_color, b_color, c_color) VALUES (:item, :size, :a_color, :b_color, :c_color)", item=item, size=size, a_color=a, b_color=b, c_color=c)

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

        ## Validation
        # Return error if missing basic entries
        if (size is None) or (a is None) or (b is None):
            return render_template('error.html', errcode='403', errmsg='Invalid entry. All Items must have a size and at least 2 colors.')

        # Test for presence of c_color        
        ctest = db.execute("SELECT c FROM loterias WHERE nombre=:name", name=item)

        # No c is given
        if not c:
            # But there should be a c
            if ctest[0]['c'] != '':
                return render_template('error.html', errcode='403', errmsg='Invalid entry. Required color missing.')

        # Superfulous c value is given
        else:
            if ctest[0]['c'] == '':
                return render_template('error.html', errcode='403', errmsg='Invalid entry. Too many colors selected.')

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
    db.execute("UPDATE boxprod SET qty=0")

    newloterias = db.execute("SELECT * FROM loterias")

    # Ensure that every item in projections is added to the production queue (less inventory on hand)
    for item in projections:
        nombre = item['name']
        size = item['size']
        qty = item['qty']
        a = item['a_color']
        b = item['b_color']
        c = item['c_color']
        print(f"One {nombre} produces...")

        # Queue box for production of small items
        if size == sizes[0]:
            queueboxes(name, qty)
        
        # Identify how many items exist in inventory
        items_onhand = db.execute("SELECT COUNT(id) FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color",
                        name=nombre, size=size, a_color=a, b_color=b, c_color=c)
        items_onhand = items_onhand[0]['count']
        
        # Subtract inventory items from projections['qty']
        qty = qty - items_onhand

       # Check for need to add parts to production queue
        if qty > 0:

            # Translate nombre to name
            name = db.execute("SELECT a FROM loterias WHERE nombre=:nombre", nombre=nombre)
            name = name[0]['a']

            # Update parts production queue
            # a_color
            queuepart(name, size, a, qty)
            # b_color
            queuepart(name, size, b, qty)
            # c_color
            if c is not None:
                queuepart(name, size, c, qty)
            # backs
            queuebacks(name, size, qty)

    return redirect("/projections")


@app.route('/box', methods=['GET', 'POST'])
@login_required
def box():
    if request.method == 'GET':
        return "#TODO"

    # Make a box on POST
    else:

        # Capture form inputs
        name = request.form.get("box")
        qty = int(request.form.get("boxqty"))

        # Fetch and update current quantity of boxes onhand and in production queue
        boxes = db.execute("SELECT * FROM boxes WHERE name=:name", name=name)
        boxprod = db.execute("SELECT * FROM boxprod WHERE name=:name", name=name)


        # Adjust inventory
        ## Update existing box inventory entry
        if boxes:
            qty_onhand = boxes[0]['qty'] + qty
            db.execute("UPDATE boxes SET qty=:qty WHERE name=:name", qty=qty_onhand, name=name)

        ## Make a new box invetory entry
        else:
            db.execute("INSERT INTO boxes (name, qty) VALUES (:name, :qty)", name=name, qty=qty)

        # Adjust production
        if boxprod:

            # Calculate new production quantity
            qty_prod = boxprod[0]['qty'] - qty

            # Update existing entry if >0
            if qty_prod > 0:
                db.execute("UPDATE boxprod SET qty=:qty WHERE name=:name", qty=qty_prod, name=name)

            # Delete existing entry if <=0
            else:
                db.execute("DELETE FROM boxprod WHERE name=:name", name=name)

        return redirect('/')


@app.route('/shipping')
@login_required
def shipping():
    return render_template('shipping.html')



###### ADMINISTRATION ######
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

            print("Computing cycle productions.")
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

            # Calculate production values
            makequeue()

            return redirect('/projections')


        # Delete a Cycle
        if path == 'delete':
            name = request.form.get("delname")
            print(name)
            if name != 'test cycle':
                db.execute("DELETE from CYCLES where name=:name", name=name)
                db.execute("UPDATE cycles SET current='TRUE' WHERE id=1")
                return render_template("message.html", message="Successfully deleted cycle.")
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
            db.execute("DROP TABLE boxes")
            db.execute("CREATE TABLE IF NOT EXISTS boxes ( \
                name VARCHAR ( 255 ), \
                qty INTEGER \
                )")

            # Create table: boxprod
            # db.execute("DROP TABLE boxprod")
            db.execute("CREATE TABLE IF NOT EXISTS boxprod ( \
                name VARCHAR ( 255 ), \
                qty INTEGER \
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


            return render_template('message.html', message="Success, tables now setup.")


        # Setup loterias
        if path == 'setup-loterias':

            # Read loterias.csv into a SQL table
            with open('static/loterias.csv', 'r') as csvfile:

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

            return render_template('message.html', message="Success, loterias updated.")


        # Not a valid admin route
        else:
            return redirect('/')



###### USER ACCOUNTS ######
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




