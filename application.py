import os
import requests
import urllib.parse
import datetime
import csv

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session, url_for, flash, send_from_directory, Markup
from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

###### DEFINITIONS ######
"""
item: fully assembled woodcut item
part: constituent piece that comprises an item, usually one of two or three
loteria: woodcut loteria pieces
"""


###### CONFIGURATION ######
# Initialize Flask App Ojbect
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

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
app.config['UPLOAD_FOLDER'] = os.getenv('PWD') + "/static/uploads"
app.config['BACKUPS'] = os.getenv('PWD') + "/static/backups"
ALLOWED_EXTENSIONS = {'csv'}

Session(app)

# Configure Heroku Postgres database
db = SQL(os.getenv('DATABASE_URL'))

# Import Authorized User List
authusers = []
authusers.append(os.getenv('USERA'))
authusers.append(os.getenv('USERB'))
authusers.append(os.getenv('USERC'))


###### TEMPLATES ######

colors = ['🖤 black', '❤️ red', '💙 TQ', '💛 yellow', '💚 green', '💜 purple']
# colors = ['black', 'red', 'turquoise', 'yellow', 'green', 'purple']
sizes = ['S', 'M', 'L']


###### DECORATORS & HELPERS ######

#
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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def gather_templates():

    # Gather template data
    loterias = db.execute("SELECT * FROM loterias")
    colors = db.execute("SELECT * FROM colors")
    sizes = db.execute("SELECT * FROM sizes")

    response = {
        'loterias': loterias,
        'colors': colors,
        'sizes': sizes
    }

    return response

def parse_sku(sku):
    # turns SKU into object with integers

    # Add leading zero, if needed
    if len(sku) == 11:
        sku = sku.zfill(12)

    if len(sku) != 12:

        flash(f"Invalid SKU length. ({len(sku)}/12 characters)")
        return redirect("/admin")

    parsed = {
        'item': (int(sku[0]) * 10) + int(sku[1]),
        'a': (int(sku[2]) * 10) + int(sku[3]),
        'b': (int(sku[4]) * 10) + int(sku[5]),
        'c': (int(sku[6]) * 10) + int(sku[7]),
        'd': (int(sku[8]) * 10) + int(sku[9]),
        'size': (int(sku[10]) * 10) + int(sku[11])
        }

    return parsed


def generate_item(templates, sku):
    # Intakes a dictionary object sku, outputs word dictionary

    # Loteria name > SKU
    for loteria in templates['loterias']:
        if loteria['sku'] == sku['item']:
            sku['item'] = loteria['nombre'] 

    # A color name > SKU
    for color in templates['colors']:
        if color['sku'] == sku['a']:
            sku['a'] = color['name']

    # B color name > SKU
    for color in templates['colors']:
        if color['sku'] == sku['b']:
            sku['b'] = color['name']

    # C color name > SKU
    for color in templates['colors']:
        if color['sku'] == sku['c']:
            sku['c'] = color['name']

    else:
        sku['c'] = ''

    # Unused placeholder
    sku['d'] = ''

    # Size name > SKU
    for size in templates['sizes']:
        if size['sku'] == sku['size']:
            sku['size'] = size['shortname'] 

    return sku


## SKUinator!
# from names
def generate_sku(templates, item):

    # Loteria name > SKU
    for loteria in templates['loterias']:
        if loteria['nombre'] in item['name']:
            sku = str(loteria['sku']).zfill(2)
            print(f"matched {loteria['nombre']} to {item['name']}. SKU:{sku}")

    # A color name > SKU
    for color in templates['colors']:
        if color['name'] in item['a_color']:
            sku = sku + str(color['sku']).zfill(2)
            print(f"matched {color['name']} to {item['a_color']}. SKU:{sku}")

    # B color name > SKU
    for color in templates['colors']:
        if color['name'] in item['b_color']:
            sku = sku + str(color['sku']).zfill(2)
            print(f"matched {color['name']} to {item['b_color']}. SKU:{sku}")

    # C color name > SKU
    if item['c_color']:
        for color in templates['colors']:
            if color['name'] in item['c_color']:
                sku = sku + str(color['sku']).zfill(2)
                print(f"matched {color['name']} to {item['c_color']}. SKU:{sku}")

    else:
        print("no c_color found")
        sku = sku + str(00).zfill(2)

    # Unused placeholder
    sku = sku + str(00).zfill(2)

    # Size name > SKU
    for size in templates['sizes']:
        if size['shortname'] in item['size']:
            sku = sku + str(size['sku']).zfill(2)
            print(f"matched {size['longname']} to {item['size']}. SKU:{sku}")

    return sku




###### QUEUE ######

# These functions produce production table, calculating projecitons less inventory
# Negative values can dequeue items

def queuepart(name, size, color, qty):
    # Queue part(s) of specified color for production by 

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
        print(f"{size} {color} {name} production qty of {parts_inprod[0]['qty']} changed to {qty}")

    # Add new production queue entry when no entry exists and qty is positive
    else:
        if qty > 0:
            db.execute("INSERT INTO production (name, size, color, qty) VALUES (:name, :size, :color, :qty)", 
                        name=name, size=size, color=color, qty=qty)
            print(f"{qty} {size} {color} {name} inserted into production queue")

def queuebacks(name, size, qty):
    # Queue backs for production            
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
      
def queueboxes(name, qty):
    # Queue boxes for production
    print("queueboxes()")

    db.execute("DELETE FROM boxprod where qty=0")

    # How many boxes already in inventory?
    boxes_onhand = db.execute("SELECT * FROM boxes WHERE name=:name", name=name)
    if boxes_onhand:
        qty = qty - boxes_onhand[0]['qty']
    print(f"{boxes_onhand} {name} boxes in inventory.")

    # How many boxes in used inventory?
    boxused = db.execute("SELECT * FROM boxused where name=:name", name=name)
    if boxused:
        qty = qty - boxused[0]['qty']
    print(f"{boxused} {name} boxes in used inventory.")

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

def makequeue():
    # (RE)BUILDS PRODUCTION TABLE
    # Uses of queuepart(), queuebacks(), and queueboxes()

    # Identify current cycle
    cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")

    # Query for current cycle's projections
    projections = db.execute("SELECT * FROM projections WHERE cycle=:cycle", cycle=cycle[0]['id'])

    # Clear all production data
    db.execute("DELETE FROM production")
    db.execute("UPDATE boxprod SET qty=0")

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
            items_onhand = db.execute("SELECT qty FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color",
                                        name=nombre, size=size, a_color=a, b_color=b, c_color=c)

        # 2 color item
        else:
            items_onhand = db.execute("SELECT qty FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color",
                                        name=nombre, size=size, a_color=a, b_color=b)

        print(items_onhand)
        if items_onhand:
            print(f"Counting {items_onhand[0]['qty']} {size} {nombre} {a} {b} {c} in inventory.")
            items_onhand = items_onhand[0]['qty']
        
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


# TODO
# @app.context_processor
# def colors():
#     return dict(colors=colors)


###### MAIN ROUTES ######
@app.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():

    if request.method == 'GET':
        print("--- / ---")

        # Query for relevant data
        cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")
        if not cycle:
            db.execute("UPDATE cycles SET current='TRUE' WHERE name='test cycle'")
            cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")
        user = db.execute("SELECT username from users WHERE id=:id", id=session["user_id"])
        items = db.execute("SELECT * FROM items ORDER BY qty DESC, size ASC, name DESC")
        parts = db.execute("SELECT * FROM parts ORDER BY size ASC, name DESC, color ASC, qty DESC")

        #####################

        # Version 2

        templates = gather_templates()
        production = db.execute("SELECT * FROM production ORDER BY size DESC, name DESC, color DESC")

        # Build totals arrays
        totals = []
        grand_total = 0

        # print(f"totals:{totals}")

        # Build empty table
        for i in range(len(templates['sizes'])):

            # Make a list to hold each sizes's color array
            totals.append([])
            # print(f"totals:{totals}")

            for j in range(len(templates['colors'])):
    
                # Make a list to hold the color totoals
                totals[i].append([])
                # print(f"totals:{totals}")
                
                totals[i][j] = 0

            # Append one more for backs
            totals[i].append(0)
            # print(f"totals:{totals}")

        # print(f"Built totals table: {totals}")

        # Loop through each production row, adding color totals
        for row in production:
            # print("row in production")

            # Loop sizes for a match
            for i in range(len(templates['sizes'])):

                # Size match found
                if templates['sizes'][i]['shortname'] == row['size']:
                    # print("match size")

                    # For each color within the size
                    for j in range(len(templates['colors'])):

                        # Sanitize "None" into ''
                        if row['color'] == None:
                            row['color'] = ''

                        # print(f"comparing {templates['colors'][j]['name']} {row['color']}")
                        if templates['colors'][j]['name'] in row['color']:
                            # print("match color")

                            totals[i][j] += row['qty']
                            grand_total += row['qty']

                    #TODO v1.0 update get exact match instead of text search for Backs
                    # For the back of that size
                    if 'Backs' in row['name']:

                        totals[i][len(templates['colors'])] += row['qty']
                        grand_total += row['qty']

        print(f"totals:{totals}")

        # Box Production Total
        box_prod_total = db.execute("SELECT SUM(qty) FROM boxprod")
        box_prod_total = box_prod_total[0]['sum']
        grand_total += box_prod_total

        # Box Inventory & Production
        boxes = db.execute("SELECT * FROM boxes")
        boxprod = db.execute("SELECT * FROM boxprod")
        boxused = db.execute("SELECT * FROM boxused")

        time = datetime.datetime.utcnow().isoformat()
        loterias = templates['loterias']

        return render_template('index.html', production=production, boxes=boxes, boxprod=boxprod, box_prod_total=box_prod_total, boxused=boxused, loterias=loterias, sizes=sizes, \
            colors=colors, user=user, items=items, parts=parts, totals=totals, cycle=cycle, time=time, grand_total=grand_total)

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

            #TODO replicate this bug
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


@app.route('/parts/<part>', methods=['GET', 'POST'])
@login_required
def parts(part):

    if request.method == 'GET':

        if part in ['black', 'red', 'TQ', 'yellow', 'green', 'purple']:

            loterias = db.execute("SELECT * FROM loterias")
            colors = db.execute("SELECT * FROM colors")
            sizes = db.execute("SELECT * FROM sizes")


            #TODO v1.0 update, eliminate like
            part_like = '%' + part
            # part_like = part
            productions = db.execute("SELECT * FROM production WHERE color LIKE :name \
                ORDER BY qty DESC", name=part_like)

            cur_color = db.execute("SELECT * FROM colors WHERE name LIKE :name", name=part_like)            


            # for row in production:
            #     if 
            #     size = 0

            return render_template('parts.html', cur_color=cur_color[0], part=part, loterias=loterias, colors=colors, sizes=sizes, productions=productions)

        else:
            return "boxes and backs coming soon"


@app.route('/items', methods=['GET', 'POST'])
@login_required
def items():
    if request.method == 'GET':

        items = db.execute("SELECT * FROM items ORDER BY qty DESC, size ASC, name DESC")
        newloterias = db.execute("SELECT * FROM loterias")

        return render_template('items.html', items=items, loterias=newloterias, sizes=sizes, colors=colors)

    # Upon POSTing form submission
    else:
        item = request.form.get("item")
        size = request.form.get("size")
        a = request.form.get("Color A")
        b = request.form.get("Color B")
        c = request.form.get("Color C")
        qty = int(request.form.get("qty"))
        deplete = request.form.get("deplete")

        print(f"deplete:{deplete}")

        print("POST form with values:")
        print(qty, item, size, a, b, c)

        ## Validation ##

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

        if deplete == "true":
            print(f"deplete == {deplete}")

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

            # Deplete a
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

            # Deplete b
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

            # Deplete c
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

        # How many items are already on hand?
        # When c part exists, identify how many items exist in inventory
        if c is not None:
            items_onhand = db.execute("SELECT qty FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color",
                        name=item, size=size, a_color=a, b_color=b, c_color=c)

        # When no c part exists, identify number of items already onhand
        else:
            items_onhand = db.execute("SELECT qty FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color",
                            name=item, size=size, a_color=a, b_color=b)
        print(f"items on hand: {items_onhand}")


        # Make new item(s)
        if not items_onhand and qty > 0:
            db.execute("INSERT INTO items (name, size, a_color, b_color, c_color, qty) \
                        VALUES (:item, :size, :a_color, :b_color, :c_color, :qty)", \
                                item=item, size=size, a_color=a, b_color=b, c_color=c, qty=qty)

        # Update existing item quantity, deleting if new_qty == 0
        else:
            items_onhand = items_onhand[0]['qty']
            new_qty = items_onhand + qty

            if not c:
                if new_qty <= 0:
                    db.execute("DELETE FROM items WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b", \
                            item=item, size=size, a=a, b=b, qty=new_qty)
                else:
                    db.execute("UPDATE items SET qty=:qty WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b", \
                            item=item, size=size, a=a, b=b, qty=new_qty)

            else:
                if new_qty <= 0:
                    db.execute("DELETE FROM items WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b AND c_color=:c", \
                            item=item, size=size, a=a, b=b, c=c, qty=new_qty)
                else:
                    db.execute("UPDATE items SET qty=:qty WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b AND c_color=:c", \
                            item=item, size=size, a=a, b=b, c=c, qty=new_qty)

        # TODO: was this just superfluous?
        # makequeue()

        flash(f"Added to items inventory: {qty} {size} {item} ({a}, {b}, {c})")

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

        newloterias = db.execute("SELECT * FROM loterias")
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
        if not c:
            projected = db.execute("SELECT qty FROM projections WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND cycle=:cycle", \
                        name=item, size=size, a_color=a, b_color=b, cycle=cycle)

        else:
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

            if not c:
                db.execute("UPDATE projections SET qty=:updated WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND cycle=:cycle", \
                        updated=updated, name=item, size=size, a_color=a, b_color=b, cycle=cycle)
                flash(f"Added to projections: {qty} {size} {item} ({a}, {b})")

            else:
                db.execute("UPDATE projections SET qty=:updated WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color \
                        AND cycle=:cycle", \
                        updated=updated, name=item, size=size, a_color=a, b_color=b, c_color=c, cycle=cycle)
                flash(f"Added to projections: {qty} {size} {item} ({a}, {b}, {c})")

            print("Existing projection updated.")
        
        # TODO: was this also superfluous?
        # Update production table
        # makequeue()

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

    total_items = 0
    total_parts = 0

    # Ensure that every item in projections is added to the production queue (less inventory on hand)
    for item in projections:
        nombre = item['name']
        size = item['size']
        qty = item['qty']
        a = item['a_color']
        b = item['b_color']
        c = item['c_color']
        print(f"One {nombre} produces...")

        total_items += qty

        # Queue box for production of small items
        if size == sizes[0]:
            total_parts += qty
            queueboxes(nombre, qty)


        # Identify how many items exist in inventory
        items_onhand = db.execute("SELECT qty FROM items WHERE name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color",
                        name=nombre, size=size, a_color=a, b_color=b, c_color=c)
        print(items_onhand)
        if items_onhand:
            items_onhand = items_onhand[0]['qty']
        else:
            items_onhand = 0

        # Subtract inventory items from projections['qty']
        qty = qty - items_onhand

       # Check for need to add parts to production queue
        if qty > 0:

            # Translate nombre to name
            name = db.execute("SELECT a FROM loterias WHERE nombre=:nombre", nombre=nombre)
            name = name[0]['a']

            # Update parts production queue
            # a_color
            total_parts += qty
            queuepart(name, size, a, qty)
            # b_color
            total_parts += qty
            queuepart(name, size, b, qty)
            # c_color
            if c is not None:
                total_parts += qty
                queuepart(name, size, c, qty)
            # backs
            total_parts += qty
            queuebacks(name, size, qty)

    flash(f"Projections (re)calculated! {total_items} items require {total_parts} parts and boxes.")
    return redirect("/projections")


@app.route('/box', methods=['POST'])
@login_required
def box():

    # Capture form inputs
    name = request.form.get("box")
    qty = int(request.form.get("boxqty"))
    action = request.form.get("action")

    # Fetch current quantity of boxes onhand
    boxes = db.execute("SELECT * FROM boxes WHERE name=:name", name=name)

    # Make a box
    if action == 'make':

        # Fetch current quantity of boxes in production queue
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

    flash("Box made.")

    # Use a box
    if action == 'use':

        # Fetch current quantity of used boxes in inventory
        boxused = db.execute("SELECT * FROM boxused WHERE name=:name", name=name)

        # Adjust inventory
        ## Update existing box inventory entry
        if boxes:

            # Deplete box inventory
            new_qty = boxes[0]['qty'] - qty
            if new_qty > 0:
                db.execute("UPDATE boxes SET qty=:qty WHERE name=:name", qty=new_qty, name=name)
            else:
                db.execute("DELETE FROM boxes WHERE name=:name", name=name)

        # Add to boxused inventory
        if boxused:

            # Calculate new quantity and update boxused inventory
            new_qty = boxused[0]['qty'] + qty
            db.execute("UPDATE boxused SET qty=:qty WHERE name=:name", qty=new_qty, name=name)

        # Make new boxused inventory
        else:
            db.execute("INSERT INTO boxused (name, qty) VALUES (:name, :qty)", name=name, qty=qty)
    
    flash("Box used.")
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
    loterias = db.execute("SELECT * FROM loterias")
    sizes = db.execute("SELECT * FROM sizes")
    colors = db.execute("SELECT * FROM colors")

    return render_template('admin.html', cycles=cycles, loterias=loterias, sizes=sizes, colors=colors)


@app.route('/admin/<path>', methods=['GET', 'POST'])
@login_required
def config(path):

    if request.method == 'GET':


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


            # Create table: colors
            db.execute("CREATE TABLE IF NOT EXISTS colors ( \
                sku INTEGER PRIMARY KEY NOT NULL, \
                name VARCHAR ( 255 ), \
                emoji VARCHAR ( 255 ) \
                )")

            colors = [['black', '⬛'],['red', '🟥'], ['TQ', '🟦'], ['yellow', '🟨'], ['green', '🟩'], ['purple', '🟪'], ['white', '⬜']]
            for i in range(len(colors)):
                db.execute("INSERT INTO colors (sku, name, emoji) VALUES (:sku, :name, :emoji)", sku=(i+1), name=colors[i][0], emoji=colors[i][1])


            # Create table: sizes
            db.execute("CREATE TABLE IF NOT EXISTS sizes ( \
                sku INTEGER PRIMARY KEY NOT NULL, \
                shortname VARCHAR ( 255 ), \
                longname VARCHAR ( 255 ) \
                )")

            sizes = [['S', 'small'], ['M', 'medium'], ['L', 'large']]
            for i in range(len(sizes)):
                db.execute("INSERT INTO sizes (sku, shortname, longname) VALUES (:sku, :shortname, :longname)", sku=(i+1), shortname=sizes[i][0] , longname=sizes[i][1])


            # Create table: recent
            # db.execute("CREATE TABLE IF NOT EXISTS recent ( \
            #     user_id INTEGER, \
            #     projection VARCHAR ( 255 ), \
            #     item VARCHAR ( 255 ), \
            #     part VARCHAR ( 255 ), \
            #     PRIMARY KEY(user_id), \
            #     CONSTRAINT
            # )")


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
                name VARCHAR ( 255 ) NOT NULL, \
                size VARCHAR ( 255 ) NOT NULL, \
                a_color VARCHAR ( 255 ), \
                b_color VARCHAR ( 255 ), \
                c_color VARCHAR ( 255 ), \
                qty INTEGER \
                )")

            # Create table: boxes
            # db.execute("DROP TABLE boxes")
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
            
            # Create table: boxused
            # db.execute("DROP TABLE boxused")
            db.execute("CREATE TABLE IF NOT EXISTS boxused ( \
                name VARCHAR ( 255 ), \
                qty INTEGER \
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


            # EXPERIMENTAL
            # Create table: summary
            # db.execute("DROP TABLE summary")
            db.execute("CREATE TABLE IF NOT EXISTS summary ()")

            flash("Tables setup.")
            return redirect("/admin")


        # Not a valid admin route
        else:
            return redirect('/')

    # On POST
    else:

        # Setup loterias
        if path == 'setup-loterias':

            # https://flask.palletsprojects.com/en/2.0.x/patterns/fileuploads/

            # check if the post request has the file part
            if 'inputfile' not in request.files:
                flash('No file part')
                return redirect("/admin")

            file = request.files['inputfile']

            # If the user does not select a file, the browser submits an empty file without a filename.
            if file.filename == '':
                flash('No selected file')
                return redirect("/admin")

            if file and allowed_file(file.filename):
                filename_user = secure_filename(file.filename) # User supplied filenames kept
                filename = 'loterias.csv'
                print(f"filename:{filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                # Read loterias.csv into a SQL table
                with open('static/uploads/loterias.csv', 'r') as csvfile:

                    print('Reading loterias.csv...')
                    csv_reader = csv.reader(csvfile)

                    db.execute("CREATE TABLE IF NOT EXISTS loterias ( \
                        nombre VARCHAR (255) NOT NULL, \
                        a VARCHAR (255), \
                        b VARCHAR (255), \
                        c VARCHAR (255), \
                        backs VARCHAR (255), \
                        sku INTEGER \
                        )")

                    db.execute("DELETE from loterias")

                    next(csv_reader)
                    counter = 0
                    for row in csv_reader:
                        counter += 1
                        db.execute("INSERT INTO loterias (sku, nombre, a, b, c, backs) VALUES (:sku, :nombre, :a, :b, :c, :backs)", \
                                        sku=row[0], nombre=row[1], a=row[2], b=row[3], c=row[4], backs=row[5])

                flash(f"Loterias updated with {counter} items.")

            else:
                flash(f"Upload failure.")

            return redirect('/admin')


        # Change or make new event
        if path == 'new-event':

            print("Computing cycle productions.")
            name = request.form.get("name")
            print(f"name:{name}")

            # Make all other cycles not current

            # Change current cycle selection
            if not name:
                cycle_id = request.form.get("cycle")
                print(f"cycle:{cycle_id}")

                # Change active cycle
                db.execute("UPDATE cycles SET current='FALSE'")
                db.execute("UPDATE cycles SET current='TRUE' WHERE id=:id", id=cycle_id)

                # Flash confirmation message
                name = db.execute("SELECT name FROM cycles WHERE id=:id", id=cycle_id)
                flash(f"{name[0]['name']} queue built.")

            # Make a new cycle
            else:
                # Create new Cycle
                db.execute("UPDATE cycles SET current='FALSE'")
                time = datetime.datetime.utcnow().isoformat()
                db.execute("INSERT INTO cycles (name, created_on, current) VALUES (:name, :time, 'TRUE')", name=name, time=time)

            # Calculate production values
            makequeue()

            return redirect('/admin')


    # Imports

        # Import event projections
        if path == 'import-event':

            event = request.form.get("event")
            print(f"event:{event}")

            # https://flask.palletsprojects.com/en/2.0.x/patterns/fileuploads/

            # check if the post request has the file part
            if 'inputfile' not in request.files:
                flash('No file part')
                return redirect("/admin")

            file = request.files['inputfile']

            # If the user does not select a file, the browser submits an empty file without a filename.
            if file.filename == '':
                flash('No selected file')
                return redirect("/admin")

            if file and allowed_file(file.filename):
                filename_user = secure_filename(file.filename) # User supplied filenames kept
                filename = 'temp.csv'
                print(f"filename:{filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                with open('static/uploads/temp.csv', 'r') as csvfile:

                    csv_reader = csv.reader(csvfile)

                    db.execute("CREATE TABLE IF NOT EXISTS test ( \
                        name VARCHAR (255), \
                        sku VARCHAR (255), \
                        size VARCHAR (255), \
                        a VARCHAR (255), \
                        b VARCHAR (255), \
                        c VARCHAR (255), \
                        qty INTEGER \
                        )")

                    print("    name    |    colors    |    sku    |    catgory    |    qty   ")
    
                    total = 0
                    skipped = 0

                    next(csv_reader)
                    for row in csv_reader:
                        total += 1

                        if row[2]:
                            sku = parse_sku(row[2])
                            print(f"Found:{sku}")

                        else:
                            skipped += 1

                        print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")

                        db.execute("INSERT INTO test (name, sku, a, b, qty) VALUES (:name, :sku, :a, :b, :qty)", \
                                        name=row[0], a=row[1], sku=row[2], b=row[3], qty=row[4])

                total 
                cycle_name = db.execute("SELECT name FROM cycles WHERE id=:event", event=event)

                flash(f"""Processed "{filename_user}" into database for event "{cycle_name[0]['name']}." {skipped}/{total} failed (no SKU).""")

            return redirect('/admin')



            # # Read loterias.csv into a SQL table
            # with open(file, 'r') as csvfile:

            #     csv_reader = csv.reader(csvfile)

            #     for row in csv_reader:
            #         print(f"row:")
            #         # db.execute("INSERT INTO loterias (nombre, a, b, c, backs) VALUES (:nombre, :a, :b, :c, :backs)", \
            #         #                 nombre=row[0], a=row[1], b=row[2], c=row[3], backs=row[4])


        if path == 'import-inventory':
            type = request.form.get('type')

            if type == 'items':

                # https://flask.palletsprojects.com/en/2.0.x/patterns/fileuploads/

                # check if the post request has the file part
                if 'inputfile' not in request.files:
                    flash('No file part')
                    return redirect("/admin")

                file = request.files['inputfile']

                # If the user does not select a file, the browser submits an empty file without a filename.
                if file.filename == '':
                    flash('No selected file')
                    return redirect("/admin")

                if file and allowed_file(file.filename):
                    filename_user = secure_filename(file.filename) # User supplied filenames kept
                    filename = 'temp.csv'
                    print(f"filename:{filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    with open('static/uploads/temp.csv', 'r') as csvfile:

                        csv_reader = csv.reader(csvfile)

                        db.execute("CREATE TABLE IF NOT EXISTS test ( \
                            name VARCHAR (255), \
                            sku VARCHAR (255), \
                            size VARCHAR (255), \
                            a VARCHAR (255), \
                            b VARCHAR (255), \
                            c VARCHAR (255), \
                            qty INTEGER \
                            )")

                        print("    name    |    colors    |    sku    |    catgory    |    qty   ")
        
                        total = 0
                        skipped = 0

                        next(csv_reader)
                        for row in csv_reader:
                            total += 1

                            if row[2]:
                                sku = parse_sku(row[2])
                                print(f"Found:{sku}")

                            else:
                                skipped += 1

                            print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")

                            db.execute("INSERT INTO test (name, sku, a, b, qty) VALUES (:name, :sku, :a, :b, :qty)", \
                                            name=row[0], a=row[1], sku=row[2], b=row[3], qty=row[4])

                    total 
                    cycle_name = db.execute("SELECT name FROM cycles WHERE id=:event", event=event)

                    flash(f"""Processed "{filename_user}" into database for event "{cycle_name[0]['name']}." {skipped}/{total} failed (no SKU).""")

                return redirect('/admin')



            if type == 'parts':
                return 'parts'


    # Backups

        if path == 'backup-projections':

            cycle = request.form.get("backup-projections")

            # BACKUP PROJECTIONS
            # Create new csv file
            with open('static/backups/backup_projections.csv', 'w') as csvfile:

                # Create writer object
                scribe = csv.writer(csvfile)

                # Pull all projections data
                templates = gather_templates()
                cycle = db.execute("SELECT * FROM cycles WHERE id=:cycle", cycle=cycle)
                projections = db.execute("SELECT * FROM projections WHERE cycle=:cycle", cycle=cycle[0]['id'])

                # Headers
                scribe.writerow(['name', 'size', 'sku', 'a_color', 'b_color', 'c_color', 'd_unused', 'qty', 'cycle'])

                for row in projections:

                    sku = generate_sku(templates, row)

                    # Write projections into csv
                    print("Scribe is writing a row...")
                    scribe.writerow([row['name'], row['size'], sku, row['a_color'], row['b_color'], row['c_color'], '', row['qty'], row['cycle']])

            time = datetime.datetime.utcnow().isoformat()
            attachname = 'backup_projections_' + cycle[0]['name'] + ' ' + time + '.csv'

            return send_from_directory(app.config['BACKUPS'], filename='backup_projections.csv', attachment_filename=attachname, as_attachment=True, mimetype='text/csv')


        if path == 'backup-inventory-parts':

            cycle = request.form.get("backup-parts")
            templates = gather_templates()

            # BACKUP PARTS
            # Create new csv file
            with open('static/backups/parts_inventory.csv', 'w') as csvfile:

                # Create writer object
                scribe = csv.writer(csvfile)

                # Pull all parts data
                parts = db.execute("SELECT * FROM parts")

                # Write headers
                # Skulet is a little sku missing the first two digits for the item identifier. 
                    # It associates colors and sizes, but does not associate the part name by means of numbers
                scribe.writerow(['skulet', 'name', 'size',  'color', 'qty'])

                # Write parts into csv
                for row in parts:

                    sku = '00'

                    # A color name > SKU
                    for color in templates['colors']:
                        if color['name'] in row['color']:
                            sku = sku + str(color['sku']).zfill(2)
                            print(f"matched {color['name']} to {row['color']}. SKU:{sku}")

                    sku = sku + '000000'

                    # Size name > SKU
                    for size in templates['sizes']:
                        if size['shortname'] in row['size']:
                            sku = sku + str(size['sku']).zfill(2)
                            print(f"matched {size['longname']} to {row['size']}. SKU:{sku}")

                    print("Scribe is writing a row...")
                    scribe.writerow([sku, row['name'], row['size'],  row['color'], row['qty']])

            time = datetime.datetime.utcnow().isoformat()
            attachname = 'parts_inventory' + time + '.csv'

            return send_from_directory(app.config['BACKUPS'], filename='parts_inventory.csv', as_attachment=True, attachment_filename=attachname, mimetype='text/csv')


        if path == 'backup-inventory-items':

            cycle = request.form.get("backup-items")
            templates = gather_templates()

            # BACKUP PARTS
            # Create new csv file
            with open('static/backups/items_inventory.csv', 'w') as csvfile:

                # Create writer object
                scribe = csv.writer(csvfile)

                # Pull all items data
                items = db.execute("SELECT * FROM items")
    
                # Write headers
                scribe.writerow(['sku', 'name', 'size', 'a_color', 'b_color', 'c_color', 'd_unused', 'qty'])

                # Write items into csv
                for row in items:

                    sku = generate_sku(templates, row)

                    print("Scribe is writing a row...")
                    scribe.writerow([sku, row['name'], row['size'], row['a_color'], row['b_color'], row['c_color'], '', row['qty']])

            time = datetime.datetime.utcnow().isoformat()
            attachname = 'items_inventory' + time + '.csv'

            return send_from_directory(app.config['BACKUPS'], filename='items_inventory.csv', as_attachment=True, attachment_filename=attachname, mimetype='text/csv')


        if path == 'download-loterias':

            file = 'loterias.csv'
            time = datetime.datetime.utcnow().isoformat()
            attachname = 'loterias_' + time + '.csv'

            print(f"/downloading: {file}")
            return send_from_directory(app.config["UPLOAD_FOLDER"], file, attachment_filename=attachname, as_attachment=True)


    # Misc

        if path == 'cycle':

            cycle = request.form.get("cycle")
            db.execute("UPDATE cycles SET current='FALSE'")
            db.execute("UPDATE cycles SET current='TRUE' WHERE id=:id", id=cycle)

            return redirect('/production')


        if path == 'wipe':

            print("/admin/wipe")

            items = request.form.get("wipe-items")
            parts = request.form.get("wipe-parts")
            boxes = request.form.get("wipe-boxes")
            usedboxes = request.form.get("wipe-usedboxes")
            projections = request.form.get("wipe-projections")

            print(items)

            if items == 'true':
                # Wipe items
                db.execute("DELETE FROM items")
                return render_template('message.html', message="Success, items wiped.")

            if parts == 'true':
                # Wipe parts
                db.execute("DELETE FROM parts")
                return render_template('message.html', message="Success, parts wiped.")

            if boxes == 'true':
                # Wipe used boxes
                db.execute("DELETE FROM boxused")
                return render_template('message.html', message="Success, used boxes wiped.")

            if usedboxes == 'true':
                # Wipe boxes
                db.execute("DELETE FROM boxes")
                return render_template('message.html', message="Success, boxes wiped.")

            if projections == 'true':
                # Wipe projections
                # Identify current cycle
                active = db.execute("SELECT id, name, created_on FROM cycles WHERE current='TRUE'")
                print(f"active cycle:{active}")
                cycle = active[0]['id']

                db.execute("DELETE FROM projections where cycle=:cycle", cycle=cycle)
                return render_template('message.html', message="Success, current event's projections wiped.")

            #TODO create counter and return number of sucessful rows per action
            flash("Setup changes complete.")
            return redirect("/admin")


        if path == 'delete-event':

            name = request.form.get("delname")
            print(name)
            if name != 'test cycle':
                db.execute("DELETE from CYCLES where name=:name", name=name)
                db.execute("UPDATE cycles SET current='TRUE' WHERE id=1")
                flash(f"Successfully deleted {name} event cycle.")
                return redirect("/admin")
            else:
                return render_template("error.html", errcode="403", errmsg="Test cycle may not be deleted.")

    # SKU

        if path == 'parse-sku':

            print("/test")
            sku = request.form.get("sku")
            print(f"sku:{sku}")
            
            # Convert string into dict object with integers
            sku = parse_sku(sku)

            templates = gather_templates()
            item = generate_item(templates, sku)

            return item


        if path == 'make-sku':
             
            nombre = str(request.form.get("nombre")).zfill(2)
            a = str(request.form.get("a")).zfill(2)
            b = str(request.form.get("b")).zfill(2)
            c = str(request.form.get("c")).zfill(2)
            d = str("00")   
            # d = str(request.form.get("d")).zfill(2)
            size = str(request.form.get("size")).zfill(2)

            sku = nombre + a + b + c + d + size

            # flash(f"SKU: {sku}")
            message = Markup(f"""
            <div class="row justify-content-center">
                <form class="form-inline">
                    <label for="sku">SKU: </label>
                    <input type="text" readonly class="form-control" id="sku" value="{sku}"> 
                    <button type="submit" class="btn btn-primary" id="copy">Copy</button>
                </form>
            </div>            
            """)

            flash(message)
            return redirect("/admin#sku")


        else:
            #TODO

            return "how did I get here?"


# TODO universalize upload process to scale a DRY approach to file serving
# Current file serving routes can validate and appropriate file name,
# ... then request /downloads to engage in download process

# @app.route('/downloads', methods=['POST'])
# @login_required
# def downloads():
#     file = request.form.get("file")
#     print(f"/downloading: {file}")
#     return send_from_directory(app.config["UPLOAD_FOLDER"], file, as_attachment=True)


# @app.route('/test', methods=['GET', 'POST'])
# @login_required
# def test():



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
