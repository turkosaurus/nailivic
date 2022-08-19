# from difflib import restore
import os
import requests
# import urllib.parse
import time
import datetime
import csv
import shopify
import json
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from flask import Flask, redirect, render_template, request, session, \
    url_for, flash, send_from_directory, Markup, g
from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
# from termcolor import colored
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import allowed_file, parse_sku, build_production, build_totals, \
    generate_item, generate_sku
from database import migrate_users, migrate_events, restore_event, fetchDict, gather_templates, \
    drop_tables, initialize_database, setup_loterias, restore_items, restore_parts

from dotenv import load_dotenv
load_dotenv()


###### DEFINITIONS ######
"""
item: fully assembled woodcut item
part: constituent piece that comprises an item, usually one of two or three
loteria: woodcut loteria pieces
cycle: a single event or series of events, used for creating projections
event: renamed cycles for clarity
"""

# print(f"Fork: {os.fork()}")

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


Session(app)

# Import Authorized User List
authusers = []
authusers.append(os.getenv('USERA'))
authusers.append(os.getenv('USERB'))
authusers.append(os.getenv('USERC'))

###### DATABASE ######

# Setup PostgreSQL database connection
conn = None
og = os.getenv('DATABASE_URL')
dev = os.getenv('HEROKU_POSTGRESQL_PURPLE_URL')
prod = os.getenv('HEROKU_POSTGRESQL_BLUE_URL')


# Testing
if os.getenv('FLASK_ENV') == 'development':
    print("Starting in DEBUG. Connecting to DEVELOPMENT database...", end="")
    db = dev

# Production
else:
    print("Connecting to PRODUCTION database...", end="")
    db = prod

# # Cold Start Initialization
# if int(os.getenv('COLD_START')) == 1:
#     print("Dropping Tables and Initializing Database...", end="")
#     drop_tables(conn)
#     initialize_database(conn)
#     print("done.")


###### APP FUNCTIONS ######

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


###### MAIN ROUTES ######

@app.route('/', methods=['GET'])
@login_required
def dashboard():

    # https://www.psycopg.org/docs/usage.html
    # Note: this could be done with decorators
        # https://pythonise.com/series/learning-flask/custom-flask-decorators
    with psycopg2.connect(db) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

            if request.method == 'GET':
                print("--- / ---")

                # cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

                # Identify current cycle and retrieve data
                cur.execute("SELECT * FROM nail_cycles WHERE current='TRUE'")
                cycle = fetchDict(cur)

                if not cycle:
                    # set default as active
                    try:
                        cur.execute("UPDATE nail_cycles SET current='TRUE' WHERE id=1 RETURNING *")
                        cycle = fetchDict(cur)
                        conn.commit()
                    except Exception as e:
                        print(f"Default Event exception: {e}")
                        data = cur.execute("SELECT * FROM nail_cycles")
                        data = fetchDict(cur)
                        if not data:
                            # Seed table with Default Event
                            time = datetime.datetime.utcnow().isoformat()
                            cur.execute("INSERT INTO nail_cycles (id, name, created_on, current) \
                                VALUES ('Default Event', %s, 'TRUE')", (time,))
                            cur.execute("UPDATE nail_cycles SET current='TRUE' WHERE id=1")
                            conn.commit()

                        else:
                            cur.execute("UPDATE nail_cycles SET current='TRUE' WHERE id=1")
                            conn.commit()

                # Query for relevant data
                cur.execute("SELECT username from nail_users WHERE id=%s", (session["user_id"],))
                user = fetchDict(cur)

                templates = gather_templates(conn)

                progress = build_production(conn, templates)

                cur.execute("SELECT * FROM nail_queueParts \
                    ORDER BY size DESC, name DESC, color DESC")
                production = fetchDict(cur)

                data = build_totals(production, templates)
                print(f"data:{data}")
                totals = data['totals']
                grand_total = data['grand_total']

                cur.execute("SELECT sum(qty) FROM nail_boxprod")
                boxprod = fetchDict(cur)

                if boxprod[0]['sum'] != 0: # recently change from "is not None"
                    grand_total += boxprod[0]['sum']
                    totals[0].append(boxprod[0]['sum'])

                else:
                    # Append zero when none
                    totals[0].append(0)

                print(f"totals:{totals}")

                cur.execute("SELECT sum(qty) FROM nail_projections \
                    WHERE cycle=(SELECT id FROM nail_cycles WHERE current='TRUE')")
                projection_totals = fetchDict(cur)
                cur.execute("SELECT sum(qty) FROM nail_items")
                item_totals = fetchDict(cur)
                cur.execute("SELECT sum(qty) FROM nail_parts")
                part_totals = fetchDict(cur)
                cur.execute("SELECT sum(qty) FROM nail_queueParts")
                production_totals = fetchDict(cur)

                time = datetime.datetime.utcnow().isoformat()

                cur.close()
                return render_template('index.html',
                    templates=templates,
                    production=production,
                    user=user,
                    item_totals=item_totals,
                    part_totals=part_totals,
                    projection_totals = projection_totals,
                    production_totals = production_totals,
                    totals=totals,
                    cycle=cycle,
                    time=time,
                    progress=progress,
                    grand_total=grand_total)

            else:
                return redirect("/")


@app.route('/parts/<part>', methods=['GET', 'POST'])
@login_required
def parts(part):
    # https://www.psycopg.org/docs/usage.html
    with psycopg2.connect(db) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

            if request.method == 'GET':

                # cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

                templates = gather_templates(conn)
                build_production(conn, templates)

                # Determine if color
                is_color = False
                for color in templates['colors']:
                    if color['name'] == part:
                        cur_color = color
                        is_color = True

                if is_color == True:

                    #TODO eliminate like?
                    part_like = cur_color['name']
                    part_like = '%' + part
                    # part_like = part
                    cur.execute("SELECT * FROM nail_queueParts WHERE color LIKE %s \
                        ORDER BY qty DESC", (part_like,))
                    productions = fetchDict(cur)

                    print(cur_color)
                    cur.execute("SELECT * FROM nail_parts WHERE color LIKE %s \
                        ORDER BY size DESC, qty DESC", (part_like,))
                    inventory = fetchDict(cur)

                    if not 'recent_part' in session :
                        session['recent_part'] = 'None'
                    print(session)

                    cur.close()
                    return render_template('parts.html',
                        cur_color=cur_color,
                        templates=templates,
                        productions=productions,
                        inventory=inventory,
                        recent=session['recent_part'])

                if part == 'backs':
                    cur_color = {
                        'name': 'backs',
                        'emoji': '🍑'
                    }

                    cur.execute("SELECT * FROM nail_queueParts \
                        WHERE name LIKE '%Backs' ORDER BY qty DESC")
                    productions = fetchDict(cur)
                    cur.execute("SELECT * FROM nail_parts \
                        WHERE name LIKE '%Backs' ORDER BY size DESC, qty DESC")
                    inventory = fetchDict(cur)

                    print("part is a back...")
                    print(f"productions:{productions}")

                    if not 'recent_part' in session :
                        session['recent_part'] = 'None'

                    cur.close()
                    return render_template('parts.html',
                    cur_color=cur_color,
                    templates=templates,
                    part=part,
                    productions=productions,
                    inventory=inventory,
                    recent=session['recent_part'])

                if part == 'boxes':

                    # Box Production Total
                    cur.execute("SELECT SUM(qty) FROM nail_boxprod")
                    box_prod_total = fetchDict(cur)
                    box_prod_total = box_prod_total[0]['sum']

                    # Box Inventory & Production
                    cur.execute("SELECT * FROM nail_boxes ORDER BY qty DESC")
                    boxes = fetchDict(cur)
                    cur.execute("SELECT * FROM nail_boxprod ORDER BY qty DESC")
                    boxprod = fetchDict(cur)
                    cur.execute("SELECT * FROM nail_boxused ORDER BY qty DESC")
                    boxused = fetchDict(cur)

                    cur.close()

                    cur_color = {
                        'name': 'boxes',
                        'emoji': '📦'
                    }

                    return render_template('boxes.html',
                        cur_color=cur_color,
                        templates=templates,
                        boxes=boxes,
                        boxprod=boxprod,
                        boxused=boxused,
                        box_prod_total=box_prod_total)

                else:
                    flash("Invalid part descriptor")
                    cur.close()
                    return redirect("/")


            # Upon POSTing form submission
            else:

                part = request.form.get("part")
                size = request.form.get("size")
                color = request.form.get("color")
                qty = int(request.form.get("qty"))
                print(f"POST TO '/' with: {part}, {size}, {color}, {qty}")

                session['recent_part'] = {
                    'part': part,
                    'size': size,
                    'color': color,
                    'qty': qty
                }

                if not size:
                    
                    flash('Size must be specified for part')
                    return redirect(f'/parts/{color}')

                # Determine if part with color, or backs
                cur.execute("SELECT backs FROM nail_loterias WHERE backs=%s", (part,))
                backs_onhand = fetchDict(cur)

                # BACKS
                if backs_onhand:
                    print(f"Backs on hand: {backs_onhand}")

                    # What quantity of this part already exists?
                    cur.execute("SELECT qty FROM nail_parts WHERE \
                                        name=%s AND size=%s", \
                                        (part, size))
                    onhand = fetchDict(cur)

                    print(f"Fetching onhand backs...")
                    print(onhand)

                    # None, create new entry
                    if not onhand:
                        cur.execute("INSERT INTO nail_parts (name, size, qty) VALUES \
                                    (%s, %s, %s)", \
                                    (part, size, qty))
                        conn.commit()
                        print(f"New {size} {part} entry created with qty {qty}.")                        

                    # Update existing entry's quantity
                    else:
                        new_qty = onhand[0]['qty'] + qty

                        if new_qty < 1:
                            cur.execute("DELETE FROM nail_parts WHERE \
                                        name=%s AND size=%s", (part, size))
                            conn.commit()
                        else:
                            cur.execute("UPDATE nail_parts SET qty=%s WHERE \
                                        name=%s AND size=%s", (new_qty, part, size))
                            conn.commit()
                        print(f"Existing {size} {part} inventory quantity \
                            updated from {onhand[0]['qty']} to {new_qty}.")

                    # Update production queue
                
                    # Identify matching part that is already in production
                    cur.execute("SELECT qty FROM nail_queueParts WHERE \
                                    name=%s AND size=%s", (part, size))
                    parts_inprod = fetchDict(cur)

                    if parts_inprod:

                        # Subtract parts being made from production queue
                        new_partsprod = parts_inprod[0]['qty'] - qty

                        # Remove entry because <0
                        if new_partsprod < 1:
                            cur.execute("DELETE FROM nail_queueParts WHERE \
                                    name=%s AND size=%s", (part, size))
                            conn.commit()

                        # Update entry to new depleted quantity after accouting for newly produced parts
                        else:
                            cur.execute("UPDATE nail_queueParts SET qty=%s WHERE \
                                    name=%s AND size=%s", (new_partsprod, part, size))
                            conn.commit()

                # PARTS WITH COLORS
                else:
                    # What quantity of this part already exists?
                    cur.execute("SELECT qty FROM nail_parts WHERE \
                                        name=%s AND size=%s AND color=%s",
                                        (part, size, color))
                    onhand = fetchDict(cur)

                    print(f"Fetching onhand parts...")
                    print(onhand)

                    # None, create new entry
                    if not onhand:
                        cur.execute("INSERT INTO nail_parts (name, size, color, qty) VALUES \
                                    (%s, %s, %s, %s)", \
                                    (part, size, color, qty))
                        conn.commit()
                        print(f"New {size} {color} {part} entry created with qty {qty}.")

                    # Update existing entry's quantity
                    else:
                        new_qty = onhand[0]['qty'] + qty
                        if new_qty < 1:
                            cur.execute("DELETE FROM nail_parts WHERE \
                                        name=%s AND size=%s AND color=%s",
                                        (part, size, color))
                            conn.commit()
                        else:
                            cur.execute("UPDATE nail_parts SET qty=%s WHERE \
                                        name=%s AND size=%s AND color=%s",
                                        (new_qty, part, size, color))
                            conn.commit()
                        print(f"Existing {size} {color} {part} inventory quantity updated from \
                            {onhand[0]['qty']} to {new_qty}.")

                    # Update production queue
                
                    # Identify matching part that is already in production
                    cur.execute("SELECT qty FROM nail_queueParts WHERE \
                                    name=%s AND size=%s AND color=%s", (part, size, color))
                    parts_inprod = fetchDict(cur)

                    if parts_inprod:

                        # Subtract parts being made from production queue
                        new_partsprod = parts_inprod[0]['qty'] - qty

                        # Remove entry because <0
                        if new_partsprod < 1:
                            cur.execute("DELETE FROM nail_queueParts WHERE \
                                    name=%s AND size=%s AND color=%s",
                                    (part, size, color))
                            conn.commit()
                        # Update entry to new depleted quantity 
                        # after accouting for newly produced parts
                        else:
                            cur.execute("UPDATE nail_queueParts SET qty=%s WHERE \
                                    name=%s AND size=%s AND color=%s",
                                    (new_partsprod, part, size, color))
                            conn.commit()

                cur.close()

                templates = gather_templates(conn)
                build_production(conn, templates)

                flash(f"Sucessfully created {qty} {size} {color} {part}")
                return redirect(f'/parts/{color}')


@app.route('/items', methods=['GET', 'POST'])
@login_required
def items():
    # https://www.psycopg.org/docs/usage.html
    with psycopg2.connect(db) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

            if request.method == 'GET':
                
                templates = gather_templates(conn)
                results = build_production(conn, templates)

                # cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                cur.execute("SELECT * FROM nail_queueItems \
                    ORDER BY size DESC, name DESC, qty DESC")
                queue = fetchDict(cur)
                cur.execute("SELECT * FROM nail_items \
                    ORDER BY size DESC, name ASC, qty DESC")
                items = fetchDict(cur)
                cur.close()

                if not 'recent_item' in session :
                    session['recent_item'] = 'None'
                    print("session['recent_item'] = 'None'")
                print(f"loading items{session}")

                return render_template('items.html',
                templates=templates,
                items=items,queue=queue,
                recent=session['recent_item'])

            # Upon POSTing form submission
            else:
                item = request.form.get("item")
                size = request.form.get("size")
                a = request.form.get("color_a")
                b = request.form.get("color_b")
                c = request.form.get("color_c")
                if c == "None":
                    c = None
                qty = int(request.form.get("qty"))
                deplete = request.form.get("deplete")

                cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

                # Force boolean state
                if deplete != 'true':
                    deplete = 'false'

                session['recent_item'] = {
                    'item': item,
                    'size': size,
                    'a': a,
                    'b': b,
                    'c': c,
                    'qty': qty,
                    'deplete': deplete
                }

                print(f"session['recent_item']:{session}")

                print(f"deplete:{deplete}")

                print("POST form with values:")
                print(qty, item, size, a, b, c, deplete)

                ## Validation ##

                # Return error if missing basic entries
                if (size is None):
                    flash("Invalid entry. Size required.")
                    return redirect("/items")

                if (a is None):
                    flash("Invalid entry. A color required.")
                    return redirect("/items")

                if (b is None):
                    flash("Invalid entry. B color required.")
                    return redirect("/items")    

                # Test for appropriateness of c_color presence
                cur.execute("SELECT c FROM nail_loterias WHERE nombre=%s", (item,))
                ctest = fetchDict(cur)

                # No c is given
                if not c:
                    # But there should be a c
                    if ctest[0]['c'] != '':                
                        flash('Invalid entry. Color C required for this item.')
                        return redirect('/items')

                # Superfulous c value is given
                else:
                    if ctest[0]['c'] == '':
                        session['recent_item']['c'] = 'None'
                        flash('Invalid entry. Color C not required for this item.')
                        return redirect('/items')


                # Validation complete. Now remove from parts and add to items.

                if deplete == "true":
                    print(f"deplete == {deplete}")

                    # Deplete parts inventory
                    # Find parts names using item name
                    cur.execute("SELECT * FROM nail_loterias WHERE nombre=%s", (item,))
                    names = fetchDict(cur)

                    # Deplete backs
                    # Update inventory
                    cur.execute("SELECT qty FROM nail_parts WHERE name=%s AND size=%s",
                    (names[0]['backs'], size))
                    backs_onhand = fetchDict(cur)

                    if backs_onhand:
                        print(f'backs_onhand:{backs_onhand}')
                        new_qty = backs_onhand[0]['qty'] - qty

                        # Remove entry if update would be cause qty to be less than 1
                        if new_qty < 1:
                            cur.execute("DELETE FROM nail_parts WHERE name=%s AND size=%s",
                            (names[0]['backs'], size))
                            conn.commit()

                        # Update existing entry
                        else:
                            cur.execute("UPDATE nail_parts SET qty=%s WHERE name=%s AND size=%s",
                            (new_qty, names[0]['backs'], size))
                            conn.commit()

                    # Deplete a
                    # Update inventory
                    cur.execute("SELECT qty FROM nail_parts WHERE name=%s AND size=%s AND color=%s",
                    (names[0]['a'], size, a))
                    a_onhand = fetchDict(cur)

                    if a_onhand:
                        new_qty = a_onhand[0]['qty'] - qty

                        # Remove entry if update would be cause qty to be less than 1
                        if new_qty < 1:
                            cur.execute("DELETE FROM nail_parts \
                                WHERE name=%s AND size=%s AND color=%s",
                            (names[0]['a'], size, a))
                            conn.commit()

                        # Update existing entry
                        else:
                            cur.execute("UPDATE nail_parts SET qty=%s \
                                WHERE name=%s AND size=%s AND color=%s",
                            (new_qty, names[0]['a'], size, a))
                            conn.commit()

                    # Deplete b
                    # Update inventory
                    cur.execute("SELECT qty FROM nail_parts \
                        WHERE name=%s AND size=%s AND color=%s",
                    (names[0]['b'], size, b))
                    b_onhand = fetchDict(cur)

                    if b_onhand:
                        new_qty = b_onhand[0]['qty'] - qty

                        # Remove entry if update would be cause qty to be less than 1
                        if new_qty < 1:
                            cur.execute("DELETE FROM nail_parts WHERE name=%s AND size=%s AND color=%s",
                            (names[0]['b'], size, b))
                            conn.commit()

                        # Update existing entry
                        else:
                            cur.execute("UPDATE nail_parts SET qty=%s WHERE name=%s AND size=%s AND color=%s",
                            (new_qty, names[0]['b'], size, b))
                            conn.commit()

                    # Deplete c
                    if c:
                        # Update inventory
                        cur.execute("SELECT qty FROM nail_parts WHERE name=%s AND size=%s AND color=%s",
                        (names[0]['c'], size, c))
                        c_onhand = fetchDict(cur)
                        if c_onhand:
                            new_qty = c_onhand[0]['qty'] - qty

                            # Remove entry if update would be cause qty to be less than 1
                            if new_qty < 1:
                                cur.execute("DELETE FROM nail_parts \
                                    WHERE name=%s AND size=%s AND color=%s",
                                (names[0]['c'], size, c))
                                conn.commit()

                            # Update existing entry
                            else:
                                cur.execute("UPDATE nail_parts SET qty=%s \
                                    WHERE name=%s AND size=%s AND color=%s",
                                (new_qty, names[0]['c'], size, c))
                                conn.commit()

                # How many items are already on hand?
                # When c part exists, identify how many items exist in inventory
                if c:
                    cur.execute("SELECT qty FROM nail_items \
                        WHERE name=%s AND size=%s AND a_color=%s AND b_color=%s AND c_color=%s",
                                (item, size, a, b, c))
                    items_onhand = fetchDict(cur)

                # When no c part exists, identify number of items already onhand
                else:
                    cur.execute("SELECT qty FROM nail_items \
                        WHERE name=%s AND size=%s AND a_color=%s AND b_color=%s",
                                    (item, size, a, b))
                    items_onhand = fetchDict(cur)
                print(f"items on hand: {items_onhand}")

                # Make new item(s)
                if not items_onhand and qty > 0:
                    cur.execute("INSERT INTO nail_items \
                        (name, size, a_color, b_color, c_color, qty) \
                        VALUES (%s, %s, %s, %s, %s, %s)",
                        (item, size, a, b, c, qty))
                    conn.commit()

                # Update existing item quantity, deleting if new_qty == 0
                else:
                    if items_onhand:
                        items_onhand = items_onhand[0]['qty']
                    else:
                        items_onhand = 0

                    new_qty = items_onhand + qty

                    if not c:
                        if new_qty <= 0:
                            cur.execute("DELETE FROM nail_items \
                                WHERE name=%s AND size=%s AND a_color=%s AND b_color=%s",
                                (item, size, a, b))
                            conn.commit()
                        else:
                            cur.execute("UPDATE nail_items SET qty=%s \
                                WHERE name=%s AND size=%s AND a_color=%s AND b_color=%s",
                                (new_qty, item, size, a, b))
                            conn.commit()

                    else:
                        if new_qty <= 0:
                            cur.execute("DELETE FROM nail_items \
                                WHERE name=%s AND size=%s AND \
                                a_color=%s AND b_color=%s AND c_color=%s",
                                (item, size, a, b, c))
                            conn.commit()
                        else:
                            cur.execute("UPDATE nail_items SET qty=%s \
                                WHERE name=%s AND size=%s AND \
                                a_color=%s AND b_color=%s AND c_color=%s", \
                                (new_qty, item, size, a, b, c))
                            conn.commit()

                templates = gather_templates(conn)
                build_production(conn, templates)

                flash(f"Added to items inventory: {qty} {size} {item} ({a}, {b}, {c})")

                cur.close()
                return redirect('/items')

# TODO ensure negative values work as well here as in /items
@app.route('/projections', methods=['GET', 'POST'])
@login_required
def projections():
    # https://www.psycopg.org/docs/usage.html
    with psycopg2.connect(db) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

            if request.method == 'GET':
            
                # cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

                # Check for "current" cycle
                cur.execute("SELECT id, name, created_on FROM nail_cycles WHERE current='TRUE'")
                active = fetchDict(cur)
                current = active
                print(f"current:{current}")

                # Set newest cycle as "current" when there is none
                if not active:
                    cur.execute("SELECT id FROM nail_cycles ORDER BY id DESC LIMIT 1")
                    newest = fetchDict(cur)
                    cur.execute("UPDATE nail_cycles SET current='true' \
                        WHERE id=%", (newest[0]['id'],))
                    conn.commit()

                # Capture id of active "current" cycle
                else:
                    active = active[0]['id']
                print(f"active:{active}")

                # List all available non-current cycles
                cur.execute("SELECT id, name, created_on FROM nail_cycles WHERE current='FALSE'")
                cycles = fetchDict(cur) 

                cur.execute("SELECT * FROM nail_projections")
                all_projections = fetchDict(cur) 

                # Sum total for inactive cycles
                for cycle in cycles:
                    cycle['total'] = 0
                    for projection in all_projections:
                        if projection['cycle'] == cycle['id']:
                            cycle['total'] += projection['qty']

                # TODO fix active cycle summation above
                # # Sum total for active cycle
                # for projection in all_projections:
                #     if projection['cycle'] == current[0]['id']:
                #         current[0]['total'] += projection['qty']
                
                print(f"cycles:{cycles}")

                cur.execute("SELECT sum(qty) FROM nail_projections where cycle=%s", (active,))
                total = fetchDict(cur)

                templates = gather_templates(conn)

                if not 'recent_projection' in session :
                    session['recent_projection'] = 'None'

                # Select projections from current cycle only
                cur.execute("SELECT * FROM nail_projections \
                    WHERE cycle=%s ORDER BY size DESC, name DESC, qty DESC", (active,))
                projections = fetchDict(cur)
                cur.close()

                return render_template('projections.html',
                templates=templates,
                projections=projections,
                current=current,
                cycles=cycles,
                total=total,
                recent=session['recent_projection'])

            # Upon POSTing form submission
            else:
                # cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

                item = request.form.get("item")
                size = request.form.get("size")
                a = request.form.get("color_a")
                b = request.form.get("color_b")
                c = request.form.get("color_c")
                qty = int(request.form.get("qty"))

                print("input")
                print(item, size, a, b, c, qty)

                ## Validation
                # Return error if missing basic entries
                if size == None:
                    flash("Invalid entry. Size required.")
                    return redirect('/projections')

                if a == None:
                    flash("Invalid entry. Color A required.")
                    return redirect('/projections')

                if b == None:
                    flash("Invalid entry. Color B required.")
                    return redirect('/projections')

                # Test for presence of c_color
                cur.execute("SELECT c FROM nail_loterias WHERE nombre=%s", (item,))
                ctest = fetchDict(cur)

                # No c is given
                if not c:
                    # But there should be a c
                    if ctest[0]['c'] != '':
                        flash("Invalid entry. Color C required.")
                        return redirect('/projections')

                # Superfulous c value is given
                else:
                    if ctest[0]['c'] == '':
                        flash("Invalid entry. No C color for this item.")
                        return redirect('/projections')

                session['recent_projection'] = {
                    'item': item,
                    'size': size,
                    'a': a,
                    'b': b,
                    'c': c,
                    'qty': qty,
                }

                itemdata = {
                    'name': item,
                    'size': size,
                    'a_color': a,
                    'b_color': b,
                    'c_color': c,
                    'qty': qty,
                }

                templates = gather_templates(conn)
                sku = generate_sku(templates, itemdata)
                print(f"sku:{sku}")
                    
                # Identify current cycle
                cur.execute("SELECT id, name, created_on FROM nail_cycles WHERE current='TRUE'")
                active = fetchDict(cur)
                print(f"active cycle:{active}")
                cycle = active[0]['id']

                # What quantity of this item is already in projections?
                if not c:
                    cur.execute("SELECT qty FROM nail_projections WHERE \
                                name=%s AND size=%s AND a_color=%s AND b_color=%s AND cycle=%s",
                                (item, size, a, b, cycle))
                    projected = fetchDict(cur)

                else:
                    cur.execute("SELECT qty FROM nail_projections WHERE \
                                name=%s AND size=%s AND \
                                a_color=%s AND b_color=%s AND c_color=%s AND cycle=%s",
                                (item, size, a, b, c, cycle))
                    projected = fetchDict(cur)

                print(f"Fetching projected ...")
                print(projected)

                # None, create new entry
                if not projected:
                    cur.execute("INSERT INTO nail_projections \
                        (name, size, a_color, b_color, c_color, qty, cycle, sku) VALUES \
                                (%s, %s, %s, %s, %s, %s, %s, %s)",
                                (item, size, a, b, c, qty, cycle, sku))
                    conn.commit()
                    flash(f"Added to projections: {qty} {size} {item} ({a}, {b}, {c}) [{sku}]")

                # Update existing entry's quantity
                else:
                    updated = projected[0]['qty'] + qty

                    if not c:
                        if updated < 1:
                            cur.execute("DELETE FROM nail_projections WHERE \
                                name=%s AND size=%s AND a_color=%s AND b_color=%s AND cycle=%s",
                                (item, size, a, b, cycle))
                            conn.commit()

                        else:
                            cur.execute("UPDATE nail_projections SET qty=%s WHERE \
                                name=%s AND size=%s AND a_color=%s AND b_color=%s AND cycle=%s",
                                (updated, item, size, a, b, cycle))
                            conn.commit()
            
                        flash(f"Added to projections: {qty} {size} {item} ({a}, {b})")

                    else:
                        if updated < 1:
                            cur.execute("DELETE FROM nail_projections WHERE \
                                name=%s AND size=%s AND \
                                a_color=%s AND b_color=%s AND c_color=%s AND \
                                cycle=%s",
                                (item, size, a, b, c, cycle))
                            conn.commit()

                        else:
                            cur.execute("UPDATE nail_projections SET qty=%s WHERE \
                                name=%s AND size=%s AND a_color=%s AND b_color=%s AND c_color=%s \
                                AND cycle=%s", \
                                (updated, item, size, a, b, c, cycle))
                            conn.commit()

                        flash(f"Added to projections: {qty} {size} {item} ({a}, {b}, {c})")

                    print("Existing projection updated.")
                
                cur.close()
                build_production(conn, templates)
                return redirect('/projections')


@app.route('/production', methods=['GET'])
@login_required
def production():
    # https://www.psycopg.org/docs/usage.html
    with psycopg2.connect(db) as conn:

        # (RE)BUILD PRODUCTION TABLE

        # Query for current cycle's projections
        templates = gather_templates(conn)
        build_production(conn, templates)
        
        flash(f"Projections (re)calculated.")
        return redirect("/projections")


@app.route('/box', methods=['POST'])
@login_required
def box():
    # https://www.psycopg.org/docs/usage.html
    with psycopg2.connect(db) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

            # Capture form inputs
            name = request.form.get("box")
            qty = int(request.form.get("boxqty"))
            action = request.form.get("action")

            # Fetch current quantity of boxes onhand
            cur.execute("SELECT * FROM nail_boxes WHERE name=%s", (name,))
            boxes = fetchDict(cur)

            # Make a box
            if action == 'make':

                # Fetch current quantity of boxes in production queue
                cur.execute("SELECT * FROM nail_boxprod WHERE name=%s", (name,))
                boxprod = fetchDict(cur)

                # Adjust inventory
                ## Update existing box inventory entry
                if boxes:
                    qty_onhand = boxes[0]['qty'] + qty
                    if qty_onhand < 1:
                        cur.execute("DELETE FROM nail_boxes WHERE name=%s", (name,))
                        conn.commit()

                    else:
                        cur.execute("UPDATE nail_boxes SET qty=%s WHERE name=%s", (qty_onhand, name))
                        conn.commit()

                ## Make a new box invetory entry
                else:
                    cur.execute("INSERT INTO nail_boxes (name, qty) VALUES (%s, %s)", (name, qty))
                    conn.commit()

                # Adjust production
                if boxprod:

                    # Calculate new production quantity
                    qty_prod = boxprod[0]['qty'] - qty

                    # Update existing entry if >0
                    if qty_prod > 0:
                        cur.execute("UPDATE nail_boxprod SET qty=%s WHERE name=%s", (qty_prod, name))
                        conn.commit()

                    # Delete existing entry if <=0
                    else:
                        cur.execute("DELETE FROM nail_boxprod WHERE name=%s", (name,))
                        conn.commit()

                if qty == 1:
                    flash(f"{qty} {name} box made.")
                else:
                    flash(f"{qty} {name} boxes made.")
            

            # Use a box
            if action == 'use':

                # Fetch current quantity of used boxes in inventory
                cur.execute("SELECT * FROM nail_boxused WHERE name=%s", (name,))
                boxused = fetchDict(cur)

                # Adjust inventory
                ## Update existing box inventory entry
                if boxes:

                    # Deplete box inventory
                    new_qty = boxes[0]['qty'] - qty
                    if new_qty > 0:
                        cur.execute("UPDATE nail_boxes SET qty=%s WHERE name=%s", (new_qty, name,))
                        conn.commit()

                    else:
                        cur.execute("DELETE FROM nail_boxes WHERE name=%s", (name,))
                        conn.commit()

                # Add to boxused inventory
                if boxused:

                    # Calculate new quantity and update boxused inventory
                    new_qty = boxused[0]['qty'] + qty
                    if new_qty > 0:
                        cur.execute("UPDATE nail_boxused SET qty=%s WHERE name=%s", (new_qty, name))
                        conn.commit()

                    else:
                        cur.execute("DELETE FROM nail_boxused WHERE name=%s", (name,))
                        conn.commit()


                # Make new boxused inventory
                else:
                    cur.execute("INSERT INTO nail_boxused (name, qty) VALUES (%s, %s)", (name, qty))
                    conn.commit()

                if qty == 1:
                    flash(f"{qty} {name} box used.")
                else:
                    flash(f"{qty} {name} boxes used.")

            cur.close()
            return redirect('/parts/boxes')


@app.route('/shipping')
@login_required
def shipping():
    return render_template('shipping.html')


###### ADMINISTRATION ######
@app.route('/admin', methods=['GET'])
@login_required
def admin():
    # conn = get_conn()
    # reconnect(conn)

    # https://www.psycopg.org/docs/usage.html
    with psycopg2.connect(db) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

            templates = gather_templates(conn)

            # cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

            cur.execute("SELECT * FROM nail_cycles ORDER BY id ASC")
            cycles = fetchDict(cur)

            cur.execute("SELECT username, last_login FROM nail_users ORDER BY last_login DESC")
            users = fetchDict(cur)

            cur.close()

    print("TEST prints to check the formatting")
    print(cycles)
    print(users)

    if os.getenv('FLASK_ENV') == "development":
        development = True
    else:
        development = False

    return render_template('admin.html',
        templates=templates,
        cycles=cycles,
        users=users,
        development=development)


@app.route('/admin/<path>', methods=['GET', 'POST'])
@login_required
# @reconnect
def config(path):

    if request.method == 'GET':
        # Not a valid admin route
        return redirect('/')

    # On POST
    else:

        # https://www.psycopg.org/docs/usage.html
        with psycopg2.connect(db) as conn:

            if path == 'migrate-events':
                status = migrate_events(conn)
                flash(status)
                return redirect("/admin")
            
            if path == 'migrate-users':
                status = migrate_users(conn)
                flash(status)
                return redirect("/admin")

            if path == 'restore':
                restore_event(conn, 1)
                resultsItem = restore_items(conn)
                resultsParts = restore_parts(conn)
                flash(f"Items:{resultsItem} Parts{resultsParts}")
                return redirect("/admin")


            if path == 'reinitialize-database':
                drop_tables(conn)
                initialize_database(conn)

                flash("Database reset and initialized.")
                return redirect("/admin")

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
                    counter = setup_loterias()
                    print(f"Loterias updated with {counter} items.")
                    flash(f"Loterias updated with {counter} items.")

                else:
                    flash(f"Upload failure.")

                return redirect('/admin')


            # Change or make new event
            if path == 'new-event':

                name = request.form.get("name")
                print(f"name:{name}")

                # Require name
                if not name:

                    # Flash confirmation message
                    flash(f"Name required to create new event.")

                # Make a new cycle
                else:
                    # Create new Cycle
                    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                    time = datetime.datetime.utcnow().isoformat()
                    cur.execute("INSERT INTO nail_cycles (name, created_on, current) \
                        VALUES (%s, %s, 'FALSE')", (name, time))
                    conn.commit()
                    cur.close()
                    flash(f'Created new event "{name}"')
                
                return redirect('/admin')


        # Imports

            # Import event projections
            if path == 'import-event':

                event = request.form.get("event")
                templates = gather_templates(conn)

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
                    filename = 'event.csv'
                    print(f"filename:{filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    results = restore_event(conn, event)

                    print(results)

                    flash(f"""Processed {results['added']}/{results['total']} items \
                        from "{filename_user}" into database for event \
                        "{results['cycle_name'][0]['name']}." \
                        {results['skipped']} failures on lines \
                        {results['err_lines']} {results['errors']}""")

                else:
                    flash("Unknown file type error.")
                    return redirect('/admin')

                return redirect('/admin')


            if path == 'import-inventory':

                type = request.form.get('type')
                event = request.form.get('event')

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
                        filename = 'items_inventory.csv'
                        print(f"filename:{filename}")
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                        results = restore_items(conn)

                        print(f'results:{results}')

                        flash(f"""Deleted {results['deleted']} old inventory items. \
                            Processed "{filename_user}" into items inventory. \
                            {results['skipped']}/{results['total']} failed (no SKU).""")

                    else:
                        flash("File processing error. Filename may be disallowed.")

                    return redirect('/admin')


                if type == 'parts':
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
                        filename = 'parts_inventory.csv'
                        print(f"filename:{filename}")
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                        results = restore_items()

                    flash(f"""Deleted {results.deleted} old inventory parts. \
                        Processed "{filename_user}" into parts inventory. \
                        {results.skipped}/{results.total} failed (no SKU).""")

                    return redirect('/admin')

                else:
                    flash("Invalid inventory import type.")
                    return redirect('/admin')


        # Backups

            if path == 'backup-projections':

                cycle = request.form.get("backup-projections")

                # BACKUP PROJECTIONS
                # Create new csv file
                with open('static/backups/backup_projections.csv', 'w') as csvfile:

                    # Create writer object
                    scribe = csv.writer(csvfile)

                    # Pull all projections data
                    templates = gather_templates(conn)
    
                    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                    cur.execute("SELECT * FROM nail_cycles WHERE id=%s", (cycle,))
                    cycle = fetchDict(cur)
                    cur.execute("SELECT * FROM nail_projections WHERE cycle=%s", (cycle[0]['id'],))
                    projections = fetchDict(cur)
                    cur.close()

                    # Headers
                    scribe.writerow(['name', 'size', 'sku', 
                        'a_color', 'b_color', 'c_color', 'd_unused', 'qty', 'cycle'])

                    for row in projections:

                        sku = generate_sku(templates, row)

                        # Write projections into csv
                        print("Scribe is writing a row...")
                        scribe.writerow([row['name'], row['size'], sku, 
                            row['a_color'], row['b_color'], row['c_color'], '', row['qty'], row['cycle']])


                time = datetime.datetime.utcnow().isoformat()
                attachname = 'backup_projections_' + cycle[0]['name'] + ' ' + time + '.csv'

                return send_from_directory(app.config['BACKUPS'],
                    filename='backup_projections.csv',
                    attachment_filename=attachname,
                    as_attachment=True,
                    mimetype='text/csv')


            if path == 'backup-inventory':

                type = request.form.get("type")

                if type == 'parts':
                    
                    cycle = request.form.get("backup-parts")
                    templates = gather_templates(conn)

                    # BACKUP PARTS
                    # Create new csv file
                    with open('static/backups/parts_inventory.csv', 'w') as csvfile:

                        # Create writer object
                        scribe = csv.writer(csvfile)

                        # Pull all parts data
                        cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                        cur.execute("SELECT * FROM nail_parts")
                        parts = fetchDict(cur)
                        cur.close()

                        # if not parts:
                        #     flash("No parts to backup.")
                        #     return redirect('/admin')

                        # Write headers
                        # Skulet is a little sku missing the first two digits for the item identifier. 
                            # It associates colors and sizes, but does not associate the part name by means of numbers
                        scribe.writerow(['skulet', 'name', 'size',  'color', 'qty'])

                        # Write parts into csv
                        for part in parts:

                            # TODO skulet needs documentation or reference
                            sku = ''
                            print(f"chcking part:{part}")
                            for loteria in templates['loterias']:
                                for subpart in loteria.values():
                                    print(f"subpart:{subpart}")
                                    if part['name'] == subpart:
                                        print(f"matched:{part['name']} to {loteria['nombre']}/{subpart}")
                                        # Add item number
                                        sku = sku + str(loteria['sku']).zfill(2)

                                        # Add part number
                                        if part['name'] == loteria['a']:
                                            sku = sku + 'a'
                                        if part['name'] == loteria['b']:
                                            sku = sku + 'b'
                                        if part['name'] == loteria['c']:
                                            sku = sku + 'c'
                                        if part['name'] == loteria['backs']:
                                            sku = sku + 'x'

                            # Color name > SKU
                            # Check if back
                            if 'Backs' in part['name']:
                                sku = sku + str(00).zfill(2)
                                print("backs")

                            # Identify color
                            else:
                                for color in templates['colors']:
                                    print(f"partname{part['name']}")

                                    if color['name'] in part['color']:
                                        sku = sku + str(color['sku']).zfill(2)
                                        print(f"matched {color['name']} to {part['color']}. SKU:{sku}")

                            # Size name > SKU
                            for size in templates['sizes']:
                                if size['shortname'] in part['size']:
                                    sku = sku + str(size['sku']).zfill(2)
                                    print(f"matched {size['longname']} to {part['size']}. SKU:{sku}")

                            print("Scribe is writing a part...")
                            scribe.writerow([sku, part['name'], part['size'],  part['color'], part['qty']])

                    time = datetime.datetime.utcnow().isoformat()
                    attachname = 'parts_inventory_' + time + '.csv'

                    return send_from_directory(
                        app.config['BACKUPS'],
                        filename='parts_inventory.csv',
                        as_attachment=True,
                        attachment_filename=attachname,
                        mimetype='text/csv')

                if type == 'items':

                    cycle = request.form.get("backup-items")
                    templates = gather_templates(conn)

                    # BACKUP ITEMS
                    # Create new csv file
                    with open('static/backups/items_inventory.csv', 'w') as csvfile:

                        # Create writer object
                        scribe = csv.writer(csvfile)

                        # Pull all items data
                        cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                        cur.execute("SELECT * FROM nail_items")
                        items = fetchDict(cur)
                        cur.close()

                        # Write headers
                        scribe.writerow(['sku', 'name', 'size',
                            'a_color', 'b_color', 'c_color', 'd_unused', 'qty'])

                        # Write items into csv
                        for row in items:

                            sku = generate_sku(templates, row)

                            print("Scribe is writing a row...")
                            scribe.writerow([sku, row['name'], row['size'],
                                row['a_color'], row['b_color'], row['c_color'], '', row['qty']])

                    time = datetime.datetime.utcnow().isoformat()
                    attachname = 'items_inventory_' + time + '.csv'

                    return send_from_directory(
                        app.config['BACKUPS'],
                        filename='items_inventory.csv',
                        as_attachment=True,
                        attachment_filename=attachname,
                        mimetype='text/csv')


            if path == 'download-loterias':

                file = 'loterias.csv'
                time = datetime.datetime.utcnow().isoformat()
                attachname = 'loterias_' + time + '.csv'

                print(f"/downloading: {file}")
                return send_from_directory(
                    app.config["UPLOAD_FOLDER"],
                    file,
                    attachment_filename=attachname,
                    as_attachment=True)


        # Misc

            if path == 'cycle':

                cycle = request.form.get("cycle")
                cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                cur.execute("UPDATE nail_cycles SET current='FALSE'")
                cur.execute("UPDATE nail_cycles SET current='TRUE' WHERE id=%s RETURNING name",
                    (cycle,))
                conn.commit()
                event = fetchDict(cur)
                cur.close()
                flash(f"Active event changed to {event}") # TODO confirm that RETURNING works?
                return redirect('/production')


            if path == 'wipe':
                print("/admin/wipe")
            
                cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

                items = request.form.get("wipe-items")
                parts = request.form.get("wipe-parts")
                boxes = request.form.get("wipe-boxes")
                usedboxes = request.form.get("wipe-usedboxes")
                projections = request.form.get("wipe-projections")

                message = ''

                # TODO implement RETURNING for all these functions
                if items == 'true':
                    # Wipe items
                    cur.execute("DELETE FROM nail_items")
                    removed = fetchDict(cur)
                    message = str(removed) + " items deleted from inventory. "

                if parts == 'true':
                    # Wipe parts
                    cur.execute("DELETE FROM nail_parts")
                    removed = fetchDict(cur)
                    message = message + str(removed) + " items deleted from inventory. "

                if boxes == 'true':
                    # Wipe used boxes
                    cur.execute("DELETE FROM nail_boxused")
                    removed = fetchDict(cur)
                    message = message + str(removed) + " used boxes deleted from inventory. "

                if usedboxes == 'true':
                    # Wipe boxes
                    cur.execute("DELETE FROM nail_boxes")
                    
                    message = message + str(removed) + " boxes deleted from inventory. "

                if projections == 'true':
                    # Wipe projections

                    # Identify current cycle
                    cur.execute("SELECT id, name, created_on FROM nail_cycles \
                        WHERE current='TRUE'")
                    active = fetchDict(cur)
                    cycle = active[0]['id']

                    cur.execute("DELETE FROM nail_projections \
                        WHERE cycle=%s RETURNING qty", (cycle,))
                    removed = fetchDict(cur)
                    total = 0
                    for product in removed:
                        total += product['qty']
                    message += str(total) + " items removed from current event projections.\n"

                    cur.execute("DELETE FROM nail_queueParts")
                    removed = fetchDict(cur)
                    message += str(removed) + " parts removed from current event laser queue.\n"

                    cur.execute("DELETE FROM nail_boxprod")
                    removed = fetchDict(cur)
                    message += str(removed) + " boxes removed from current event laser queue.\n"

                conn.commit()
                cur.close()

                flash(message)
                return redirect("/admin")


            if path == 'delete-event':

                id = request.form.get("cycle-id")
                name = request.form.get("cycle-name")

                print(id, name)

                # Delete event (that is not the default #1 event)
                if int(id) != 1:

                    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                    cur.execute("SELECT * FROM nail_cycles WHERE id=%s", (id,))
                    deleted = fetchDict(cur)
                    cur.execute("DELETE FROM nail_cycles WHERE id=%s", (id,))
                    cur.execute("UPDATE nail_cycles SET current='TRUE' WHERE id=1")
                    cur.execute("DELETE FROM nail_projections WHERE cycle=%s", (id,))
                    projections = fetchDict(cur)
                    conn.commit()
                    cur.close()

                    flash(f"""Event cycle "{deleted[0]['name']}" and \
                        {projections} associated projections deleted.""")

                    return redirect("/admin")

                else:
                    flash("Default Event may not be deleted.")
                    return redirect("/admin") 

        # SKU

            if path == 'parse-sku':

                print("/test")
                sku = request.form.get("sku")
                print(f"sku:{sku}")
                
                # Convert string into dict object with integers
                sku = parse_sku(sku)
                print(sku)

                if sku == 'err_len':
                    flash(f"Invalid SKU length. ({len(sku)}/12 characters)")
                    return redirect("/admin")

                templates = gather_templates(conn)
                item = generate_item(templates, sku)

                flash(f"{sku['sku']}: {item['item']} - {item['a']}/{item['b']}/{item['c']} ({item['size']})")
                return redirect('/admin')


            if path == 'make-sku':
                
                nombre = str(request.form.get("nombre")).zfill(2)
                a = str(request.form.get("a")).zfill(2)
                b = str(request.form.get("b")).zfill(2)
                c = str(request.form.get("c")).zfill(2)
                type = str(request.form.get("type")).zfill(2)
                size = str(request.form.get("size")).zfill(2)

                sku = nombre + a + b + c + type + size

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
                flash("Invalid route.")
                return redirect("/admin")


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

        # https://www.psycopg.org/docs/usage.html
        with psycopg2.connect(db) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

                # Error Checking
                # Ensure username was submitted
                if not request.form.get("username"):
                    flash("Username required.")
                    return redirect('/register')

                # Ensure password was submitted
                if not request.form.get("password"):
                    flash("Password required.")
                    return redirect('/register')

                # Ensure password and password confirmation match
                if request.form.get("password") != request.form.get("passwordconfirm"):
                    flash("Passwords must match.")
                    return redirect('/register')

                # Ensure minimum password length
                if len(request.form.get("password")) < 8:
                    flash("Password must be at least 8 characters.")
                    return redirect('/register')

                # Store the hashed username and password
                username = request.form.get("username")
                hashedpass = generate_password_hash(request.form.get("password"))

                if username not in authusers:
                    flash("Unauthorized user.")
                    return redirect('/register')

                # Check if username is already taken
                # cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
                cur.execute("SELECT username FROM nail_users WHERE username LIKE %s", (username,))
                taken = fetchDict(cur)
                if not taken:
                    # Add the username
                    time = datetime.datetime.utcnow().isoformat()
                    cur.execute("INSERT INTO nail_users (username, password, created_on) \
                        VALUES (%s, %s, %s)",
                        (username, hashedpass, time))
                    conn.commit()
                    cur.close()
                    return redirect("/")

                else:
                    cur.close()
                    flash("Username invalid or already taken.")
                    return redirect('/register')


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # conn = get_conn()

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # https://www.psycopg.org/docs/usage.html
        with psycopg2.connect(db) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:

                # Ensure username was submitted
                if not request.form.get("username"):
                    flash("Username required.")
                    return redirect('/login')

                # Ensure password was submitted
                elif not request.form.get("password"):
                    flash("Password required.")
                    return redirect('/login')

                # Query database for username
                username = request.form.get("username")

                cur.execute("SELECT * FROM nail_users WHERE username=%s", (username,))
                rows = fetchDict(cur)

                # Ensure username exists
                if len(rows) != 1:
                    cur.close()
                    flash("Username not found.")
                    return redirect('/login')

                # Ensure username exists and password is correct
                if not check_password_hash(rows[0]["password"], request.form.get("password")):
                    cur.close()
                    flash("Incorrect password.")
                    return redirect('/login')

                # Remember which user has logged in
                session["user_id"] = rows[0]["id"]

                # Update "last_login"
                time = datetime.datetime.utcnow().isoformat()
                cur.execute("UPDATE nail_users SET last_login=%s WHERE id=%s",
                (time, session["user_id"]))
                conn.commit()
                cur.close()

                # Send developer directly to Admin
                if request.form.get("username") == 'Turkosaurus':
                    return redirect("/admin")

                else:
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





# @app.route('/shopifytest', methods=['GET', 'POST'])
# @login_required
# def test():
    
#     # Establish connection to Shopify
#     # https://shopify.github.io/shopify_python_api/
#     api_version = "2022-01"
#     shopify_apikey = os.getenv('SHOPIFY_API')
#     shopify_password = os.getenv('SHOPIFY_PASSWORD')
#     shop_url = "https://%s:%s@nailivic-studios.myshopify.com/admin" % (shopify_apikey, shopify_password)
#     shopify.ShopifyResource.set_site(shop_url)
#     shop = shopify.Shop.current

    
#     # Fuck it we'll do it live

#     route = f"admin/api/{api_version}/products.json"
#     # route = f"admin/api/{api_version}/inventory_items.json?"
#     # route = f"admin/products.json"
#     base_url = f"https://{shopify_apikey}:{shopify_password}@nailivic-studios.myshopify.com/{route}"

#     r = requests.get(base_url)
#     print(f"r:{r}")
#     # print(f"r:{r.content}")

#     content = json.loads(r.content)
#     # print(f"content:{content}")

#     content = content['products']

#     extracted_data = []
#     for i in content:
        
#         data = [i['id'], i['title'], i['variants'][0]['sku'], i['variants'][0]['inventory_quantity']]
#         extracted_data.append(data)

#     print(f"extracted_data:{extracted_data}")



#     return render_template("error.html", errmsg=extracted_data)




    # print(f"r:{r.json()['products'][0]['vendor']}")

    # inventory_item_id = 270107000204
    # product = shopify.InventoryItem(api_version, inventory_item_id)
    # print(f'RESULTS:{product}')


    # sku = 270107000204
    # product = shopify.InventoryItem(api_version, '*')
    # print(f'RESULTS:{product}')


    # return redirect("/admin")

