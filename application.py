import os
import requests
# import urllib.parse
import datetime
import csv
import shopify
import json

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session, url_for, flash, send_from_directory, Markup
from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
# from termcolor import colored
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


from dotenv import load_dotenv
load_dotenv()


###### DEFINITIONS ######
"""
item: fully assembled woodcut item
part: constituent piece that comprises an item, usually one of two or three
loteria: woodcut loteria pieces
cycle: a single event or series of events, used for creating projections
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



###### FUNCTIONS ######

## I/O

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


###### QUEUE ######

# These functions produce production table, calculating projections less inventory
# Negative values can dequeue items

def gather_templates():

    # Gather template data
    loterias = db.execute("SELECT * FROM loterias ORDER BY SKU ASC")
    shirts = db.execute("SELECT * FROM shirts")
    colors = db.execute("SELECT * FROM colors")
    sizes = db.execute("SELECT * FROM sizes")
    types = db.execute("SELECT * FROM types")

    response = {
        'loterias': loterias,
        'shirts': shirts,
        'colors': colors,
        'sizes': sizes,
        'types': types
    }

    return response

def parse_sku(sku):
    # turns SKU into object with integers

    # Add leading zero, if needed
    if len(sku) == 11:
        sku = sku.zfill(12)

    if len(sku) != 12:
        return 'err_len'

    print(sku)
    parsed = {
        'item': (int(sku[0]) * 10) + int(sku[1]),
        'a': (int(sku[2]) * 10) + int(sku[3]),
        'b': (int(sku[4]) * 10) + int(sku[5]),
        'c': (int(sku[6]) * 10) + int(sku[7]),
        'type': (int(sku[8]) * 10) + int(sku[9]),
        'size': (int(sku[10]) * 10) + int(sku[11]),
        'sku': sku
        }

    return parsed

def parse_skulet(sku):
    # turns SKU into object with integers

    # Add leading zero, if needed
    if len(sku) == 6:
        sku = sku.zfill(7)

    if len(sku) != 7:
        return 'err_len'

    print(sku)
    parsed = {
        'item': (int(sku[0]) * 10) + int(sku[1]),
        'part': sku[2],
        'color': (int(sku[3]) * 10) + int(sku[4]),
        'size': (int(sku[5]) * 10) + int(sku[6]),
        'sku': sku
        }

    return parsed

def generate_item(templates, sku):
    # Intakes a dictionary object with parts sku, replaces number skus with words

    named = {}

    # SKU > Loteria name
    for loteria in templates['loterias']:
        if loteria['sku'] == sku['item']:
            named['item'] = loteria['nombre']

    # SKU > Loteria name (shirts)
    for loteria in templates['shirts']:
        if loteria['sku'] == sku['item']:
            named['item'] = loteria['nombre']

    # SKU > A color name
    for color in templates['colors']:
        if color['sku'] == sku['a']:
            named['a'] = color['name']

    # SKU > B color name
    for color in templates['colors']:
        if color['sku'] == sku['b']:
            named['b'] = color['name']

    # SKU > C color name
    for color in templates['colors']:
        if color['sku'] == sku['c']:
            named['c'] = color['name']

    if sku['c'] == 0:
        named['c'] = ''

    # Type
    for type in templates['types']:
        if type['sku'] == sku['type']:
            named['type'] = type['name']

    # SKU > size name
    for size in templates['sizes']:
        if size['sku'] == sku['size']:
            named['size'] = size['shortname']
    
    if 'size' not in named.keys():
        named['error'] = 'No size given.'
    
    return named


def generate_sku(templates, item):
    # from names

    # TODO use this for error checking
    valid = {
        'name': False,
        'a': False,
        'b': False,
        'c': False,
        'size': False,
        'type': False
    }
    print(f"valid:{valid}")

    # Loteria name > SKU
    for loteria in templates['loterias']:
        if loteria['nombre'] in item['name']:
            sku = str(loteria['sku']).zfill(2)
            print(f"matched {loteria['nombre']} to {item['name']}. SKU:{sku}")
            valid['name'] = True

    # Loteria name > SKU (for shirts)
    for loteria in templates['shirts']:
        if loteria['nombre'] in item['name']:
            sku = str(loteria['sku']).zfill(2)
            print(f"matched {loteria['nombre']} to {item['name']}. SKU:{sku}")
            valid['name'] = True

    # A color name > SKU
    for color in templates['colors']:
        if color['name'] in item['a_color']:
            sku = sku + str(color['sku']).zfill(2)
            print(f"matched {color['name']} to {item['a_color']}. SKU:{sku}")
            valid['a'] = True

    # B color name > SKU
    for color in templates['colors']:
        if color['name'] in item['b_color']:
            sku = sku + str(color['sku']).zfill(2)
            print(f"matched {color['name']} to {item['b_color']}. SKU:{sku}")
            valid['b'] = True

    # C color name > SKU
    if item['c_color']:
        for color in templates['colors']:
            if color['name'] in item['c_color']:
                sku = sku + str(color['sku']).zfill(2)
                print(f"matched {color['name']} to {item['c_color']}. SKU:{sku}")
                valid['c'] = True

    else:
        print("no c_color given")
        sku = sku + str(00).zfill(2)
        valid['c'] = True

    # TODO replace with simpler if/else?
    try:
        print(80 * "X")
        for type in templates['types']:
            print(f"{type['name']}{item['type']}")
            if type['name'] == item['type']:
                print(type['sku'])
                type_num = type['sku']
    
    except:
        type_num = 0 # Laser Cuts do not specify their type, default to 0

    finally:
        sku = sku + str(type_num).zfill(2)

    # Size name > SKU
    for size in templates['sizes']:
        if size['shortname'] in item['size']:
            sku = sku + str(size['sku']).zfill(2)
            print(f"matched {size['longname']} to {item['size']}. SKU:{sku}")
            valid['size'] = True

    print(f"valid:{valid}")

    return sku

def sql_cat(lists):
    # Takes list of lists and converts them into SQL compatible string concatenations
    
    # Converts arrays:
    # [[foo, bar], [baz, bat]]
    # into strings:
    # (foo, bar), (baz, bat) 

    string = ''

    for list in lists:
        string += '('

        for value in list:
            # All the words coming in should be
            # only from the database, this is 
            # a precautionary step
            if isinstance(value, str):
                value = value.replace('-', '')
                value = value.replace("'", '')
                value = value.replace("\\", '')
                value = value.replace('"', '')
            string += f"'{value}', "
            # string += ', '

        # Remove the last 2 chars
        string = string[:-2]
        string = string + '), '

    # Remove the last 2 chars
    string = string[:-2]

    print(string)
    return string

# Unused. Testing revealed that the CS50 opens a new connection for each transaction. 
# Migration to native psychopg implementation would allow proper tuple-ization rather than contenation.
def Xsql_cat(lists):
    # print(f"before:{lists}")
    for i in range(len(lists)):
        lists[i] = tuple(lists[i])
    # print(f"after:{lists}")


    # for list in lists:
    #     lists[list] = tuple(list)

    return lists

def build_production(templates):

    projections = db.execute("SELECT * FROM projections WHERE cycle=(SELECT id FROM cycles WHERE current='TRUE')")
    items = db.execute("SELECT * FROM items")
    parts = db.execute("SELECT * FROM parts")
    boxes = db.execute("SELECT * FROM boxes UNION SELECT * FROM boxused")


    # Initiate queue list and counter
    queue = []
    i = 0 # Parts Queue Counter

    box_queue = []
    j = 0 # Box Queue Counter

    progress = {
        'item_projection': 0,
        'item_inventory': 0,
        'item_percent': 0,
        'parts_projection': 0,
        'parts_inventory': 0,
        'parts_percent': 0,
        'box_projection': 0,
        'box_inventory': 0,
        'box_percent': 0
    }


    # print(f"projections:{projections}")

    # Add each projections required parts to production queue, minus items already on hand in inventory
    # (parts will be subtracted later)
    for projection in projections:

        progress['item_projection'] += projection['qty']

        print("-" * 80)
        print(f"Projection:{projection['qty']} {projection['name']} {projection['size']} {projection['a_color']}/{projection['b_color']}/{projection['c_color']}")

        # total_projections += projection['qty']

        # Box creation for every small
        for size in templates['sizes']:

            # Small found
            if size['sku'] == 1 and size['shortname'] == projection['size']:

                # make a box
                qty = projection['qty']
                progress['box_projection'] += projection['qty']

                if qty > 0:

                    box_queue.append([])

                    # name
                    box_queue[j].append(projection['name'])
                    # qty
                    box_queue[j].append(qty)

                    j += 1

                # print(f"Make boxes {box_queue}.")

        # Subtract Items in Inventory
        for item in items:
            # print(f"item:{item}")

            # Matching item in inventory
            if item['name'] == projection['name'] and \
                item['size'] == projection['size'] and \
                item['a_color'] == projection['a_color'] and \
                item['b_color'] == projection['b_color'] and \
                item['c_color'] == projection['c_color']:

                # Subtract assembled items qty from projections qty
                projection['qty'] -= item['qty']
                progress['item_inventory'] += item['qty']

                print (f"{item['qty']} {item['size']} {item['name']} {item['a_color']}/{item['b_color']}/{item['c_color']} already in inventory")

        # Add to production all parts that existing items inventory does not satisfy
        if projection['qty'] > 0:

            print(f"{projection['qty']} {projection['name']} unmet by items inventory.")
            # print(f"projections.qty > 0 and queue:{queue}")

            # Match name to existing loteria template
            for loteria in templates['loterias']:
                if loteria['nombre'] == projection['name']:

                    qtys = {
                        'a': projection['qty'],
                        'b': projection['qty'],
                        'c': projection['qty'],
                        'backs': projection['qty']
                    }

                    print(f"Checking parts inventory for {loteria['a']}, {loteria['b']}, {loteria['c']}, {loteria['backs']}")
                    # print(qtys)

                # Add A
                    # Update existing entry or make new
                    found_existing = False
                    for line in queue:
                        # print(f"A line: {line}")

                        if line[0] == loteria['a'] and \
                            line[1] == projection['size'] and \
                            line[2] == projection['a_color']:

                            line[3] = int(line[3]) + qtys['a']

                            found_existing = True

                            # print(f"FOUND MATCHING EXISTING A:")
                            # print(f"queue:{line}")
                            # print(f"projection:{projection}")
                            # print('-' * 80)


                    if found_existing == False:

                        # print(f"MAKING NEW A:")

                        # Add a new list for the part to be made
                        queue.append([])
                        # name
                        queue[i].append(loteria['a'])
                        # size
                        queue[i].append(projection['size'])
                        # color
                        queue[i].append(projection['a_color'])
                        # qty
                        queue[i].append(f'{qtys["a"]}')
        
                        i += 1

                    # Add B

                    # Update existing entry or make new
                    found_existing = False
                    for line in queue:
                        # print(f"B line: {line}")
                        if line[0] == loteria['b'] and \
                            line[1] == projection['size'] and \
                            line[2] == projection['b_color']:

                            line[3] = int(line[3]) + qtys['b']

                            found_existing = True
                            # print("FOUND EXISTING B")

                    if found_existing == False:

                        # Add a new list for the part to be made
                        # print(f"MAKING NEW B:")

                        # Add b new list for the part to be made
                        queue.append([])

                        # name
                        queue[i].append(loteria['b'])
                        # size
                        queue[i].append(projection['size'])
                        # color
                        queue[i].append(projection['b_color'])
                        # qty
                        queue[i].append(f'{qtys["b"]}')
        
                        i += 1

                    # Add C

                    if loteria['c'] != '':

                        # Update existing entry or create new
                        found_existing = False
                        for line in queue:
                            # print(f"C line: {line}")
                            if line[0] == loteria['c'] and \
                                line[1] == projection['size'] and \
                                line[2] == projection['c_color']:

                                line[3] = int(line[3]) + qtys['c']

                                found_existing = True
                                # print("FOUND EXISTING C")

                        if found_existing == False:

                            # print(f"MAKING NEW C:")

                            # Add a new list for the part to be made
                            queue.append([])
                            # name
                            queue[i].append(loteria['c'])
                            # size
                            queue[i].append(projection['size'])
                            # color
                            queue[i].append(projection['c_color'])
                            # qty
                            queue[i].append(f'{qtys["c"]}')
            
                            i += 1

                    # Add Backs

                    # Update existing entry
                    found_existing = False
                    for line in queue:
                        if line[0] == loteria['backs'] and \
                            line[1] == projection['size']:

                            line[3] = int(line[3]) + qtys['backs']

                            found_existing = True
                            # print("FOUND EXISTING BACK")

                    if found_existing == False:

                        # print("MAKING NEW BACK")


                        # Add a new list for the part to be made
                        queue.append([])
                        # name
                        queue[i].append(loteria['backs'])
                        # size
                        queue[i].append(projection['size'])
                        # color
                        queue[i].append('')
                        # qty
                        queue[i].append(f'{qtys["backs"]}')
        
                        i += 1

    print('*' * 80)
    print("PODUCTION QUEUE BUILT, REMOVING EXISTING ITEMS INVENTORY")
    print("BEFORE")
    # print(len(queue))
    # print(queue)

    # Subtract existing parts from queue
    for q in queue:

        progress['parts_projection'] += int(q[3])

        # print(f"q:{q}")
        for part in parts:

            # Matching part found in inventory
            if part['name'] == q[0] and \
                part['size'] == q[1] and \
                part['color'] == q[2]:

                print(f"Matched {part['name']} {part['size']} {part['color']}")
                print(f"Need {q[3]}, have {part['qty']}")

                if int(q[3]) > part['qty']:
                    progress['parts_inventory'] += part['qty']
                else:
                    progress['parts_inventory'] += int(q[3])

                if part['qty'] == 0:
                    continue

                # Demand is exactly met
                elif int(q[3]) == part['qty']:
                    q[3] = 0
                    part['qty'] = 0
                
                # Demand greater than inventory
                elif int(q[3]) > part['qty']:                        

                    # How many will be used?
                    used = part['qty']

                    # Removed the used amount from production queue and available parts
                    q[3] = int(q[3]) - used
                    part['qty'] -= used

                # Inventory greater than demand
                else:
                # int(q[3]) < part['qty']

                    # How many will be used?
                    used = int(q[3])

                    # Removed the used amount from production queue and available parts
                    q[3] = 0
                    part['qty'] -= used

                print(f"Adjusted to")
                print(f"Need {q[3]}, have {part['qty']}")

    print("---")
    print("AFTER SUBTRACTING PARTS")
    # print(len(queue))
    # print(queue)
    print("*" * 80)

    # Eliminate production queue entries with quantity < 0
    tmp = []
    for q in queue:
        if int(q[3]) > 0:
            tmp.append(q)
        else:
            print(f"removing for qty=0:{q}")
    queue = tmp

    # Consolidate duplicate box_queue entries and subtract existing box inventory
    tmp = []
    i = 0
    
    for loteria in templates['loterias']:

        total = 0
        # print(f"box_queue:{box_queue}")

        # Consolidate all box entries
        # TODO check this change. box_queue[0] > box_queue['name']
        for box in box_queue:
            if box[0] == loteria['nombre']:
                total += int(box[1])
                # print(f"found {loteria['nombre']} in queue, total up to {total}")


        # Subtract existing box inventory
        for box in boxes:
            if box['name'] == loteria['nombre']:
                total -= box['qty']
                # print(f"found {loteria['nombre']} in inventory, total down to {total}")

                progress['box_inventory'] += box['qty']

        if total > 0:
            tmp.append([])
            tmp[i].append(loteria['nombre'])
            tmp[i].append(total)
            i += 1

    box_queue = tmp

    # Convert list to string
    # boxes
    print("Box List:")
    # for row in box_queue:
        # print(row)


    print(f"before:{box_queue}")
    box_queue = sql_cat(box_queue)
    print(f"after:{box_queue}")

    # print(f"String:{box_queue}")

    # parts
    print("Parts List:")
    # for row in queue:
        # print(row)

    queue = sql_cat(queue)
    # print(f"String:{queue}")

    # queue = tuplefy(queue)
    # print(f"Tuples:{queue}")

    box_added = 0
    part_added = 0

    # Wipe Box Produciton
    db.execute("DELETE FROM boxprod")
    print(f"box_queue:{box_queue}")

    # New Box Production
    if box_queue:
        print(box_queue)
        box_added = db.execute(f"INSERT INTO boxprod (name, qty) VALUES {box_queue}")

    
    # Wipe production
    db.execute("DELETE FROM production")
    # New Part Production
    if queue:
        # part_added = db.execute(f"INSERT INTO production (name, size, color, qty) VALUES {queue}")

        part_added = db.execute(f"INSERT INTO production (name, size, color, qty) VALUES {queue}")

    # tmp = {
    #     'projections': total_projections,
    #     'boxes': box_added,
    #     'parts': part_added
    # }

    try:
        progress['item_percent'] = progress['item_inventory'] / progress['item_projection'] * 100
    except:
        progress['item_percent'] = 0

    try:
        progress['parts_percent'] = progress['parts_inventory'] / progress['parts_projection'] * 100
    except:
        progress['parts_percent'] = 0

    try:
        progress['box_percent'] = progress['box_inventory'] / progress['box_projection'] * 100
    except:
        progress['box_percent'] = 0

    print(progress)
    return progress
        












@app.route('/shopifytest', methods=['GET', 'POST'])
@login_required
def test():
    
    # Establish connection to Shopify
    # https://shopify.github.io/shopify_python_api/
    api_version = "2022-01"
    shopify_apikey = os.getenv('SHOPIFY_API')
    shopify_password = os.getenv('SHOPIFY_PASSWORD')
    shop_url = "https://%s:%s@nailivic-studios.myshopify.com/admin" % (shopify_apikey, shopify_password)
    shopify.ShopifyResource.set_site(shop_url)
    shop = shopify.Shop.current

    
    # Fuck it we'll do it live

    route = f"admin/api/{api_version}/products.json"
    # route = f"admin/api/{api_version}/inventory_items.json?"
    # route = f"admin/products.json"
    base_url = f"https://{shopify_apikey}:{shopify_password}@nailivic-studios.myshopify.com/{route}"

    r = requests.get(base_url)
    print(f"r:{r}")
    # print(f"r:{r.content}")

    content = json.loads(r.content)
    # print(f"content:{content}")

    content = content['products']

    extracted_data = []
    for i in content:
        
        data = [i['id'], i['title'], i['variants'][0]['sku'], i['variants'][0]['inventory_quantity']]
        extracted_data.append(data)

    print(f"extracted_data:{extracted_data}")



    return render_template("error.html", errmsg=extracted_data)

    # print(f"r:{r.json()['products'][0]['vendor']}")

    # inventory_item_id = 270107000204
    # product = shopify.InventoryItem(api_version, inventory_item_id)
    # print(f'RESULTS:{product}')


    # sku = 270107000204
    # product = shopify.InventoryItem(api_version, '*')
    # print(f'RESULTS:{product}')


    # return redirect("/admin")








###### MAIN ROUTES ######
@app.route('/', methods=['GET'])
@login_required
def dashboard():

    if request.method == 'GET':
        print("--- / ---")

        # Identify current cycle
        cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")
        if not cycle:

            data = db.execute("SELECT * FROM cycles")
            if not data:
                # Seed table with Default Event
                time = datetime.datetime.utcnow().isoformat()
                db.execute("INSERT INTO cycles (id, name, created_on, current) VALUES ('1', 'Default Event', :time, 'TRUE')", time=time)            

            else:
                db.execute("UPDATE cycles SET current='TRUE' WHERE id=1")
            cycle = db.execute("SELECT * FROM cycles WHERE current='TRUE'")

        # Query for relevant data
        user = db.execute("SELECT username from users WHERE id=:id", id=session["user_id"])

        templates = gather_templates()

        progress = build_production(templates)

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

        boxprod = db.execute("SELECT sum(qty) FROM boxprod")

        if boxprod[0]['sum'] is not None:
            grand_total += boxprod[0]['sum']
            totals[0].append(boxprod[0]['sum'])

        else:
            # Append zero when none
            totals[0].append(0)

        print(f"totals:{totals}")

        projection_totals = db.execute("SELECT sum(qty) FROM projections WHERE cycle=(SELECT id FROM cycles WHERE current='TRUE')")
        item_totals = db.execute("SELECT sum(qty) FROM items")
        part_totals = db.execute("SELECT sum(qty) FROM parts")
        production_totals = db.execute("SELECT sum(qty) FROM production")

        time = datetime.datetime.utcnow().isoformat()

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

    if request.method == 'GET':

        templates = gather_templates()
        build_production(templates)

        # Determine if color
        is_color = False
        for color in templates['colors']:
            if color['name'] == part:
                cur_color = color
                is_color = True

        if is_color == True:

            #TODO v1.0 update, eliminate like
            part_like = cur_color['name']
            part_like = '%' + part
            # part_like = part
            productions = db.execute("SELECT * FROM production WHERE color LIKE :name \
                ORDER BY qty DESC", name=part_like)

            print(cur_color)
            inventory = db.execute("SELECT * FROM parts WHERE color LIKE :name \
                ORDER BY size DESC, qty DESC", name=part_like)
    
            if not 'recent_part' in session :
                session['recent_part'] = 'None'
            print(session)

            return render_template('parts.html', cur_color=cur_color, templates=templates, productions=productions, inventory=inventory, recent=session['recent_part'])

        if part == 'backs':
            cur_color = {
                'name': 'backs',
                'emoji': '🍑'
            }

            productions = db.execute("SELECT * FROM production WHERE name LIKE '%Backs' ORDER BY qty DESC")
            inventory = db.execute("SELECT * FROM PARTS WHERE name LIKE '%Backs' ORDER BY size DESC, qty DESC")

            print("part is a back...")
            print(f"productions:{productions}")

            if not 'recent_part' in session :
                session['recent_part'] = 'None'

            return render_template('parts.html', cur_color=cur_color, templates=templates, part=part, productions=productions, inventory=inventory, recent=session['recent_part'])

        if part == 'boxes':

            # Box Production Total
            box_prod_total = db.execute("SELECT SUM(qty) FROM boxprod")
            box_prod_total = box_prod_total[0]['sum']

            # Box Inventory & Production
            boxes = db.execute("SELECT * FROM boxes ORDER BY qty DESC")
            boxprod = db.execute("SELECT * FROM boxprod ORDER BY qty DESC")
            boxused = db.execute("SELECT * FROM boxused ORDER BY qty DESC")

            cur_color = {
                'name': 'boxes',
                'emoji': '📦'
            }

            return render_template('boxes.html', cur_color=cur_color, templates=templates, boxes=boxes, boxprod=boxprod, boxused=boxused, box_prod_total=box_prod_total)

        else:
            flash("Invalid part descriptor")
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

                if new_qty < 1:
                    db.execute("DELETE FROM parts WHERE \
                                name=:name AND size=:size", name=part, size=size)
                else:
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

            # None, create new entry
            if not onhand:
                db.execute("INSERT INTO parts (name, size, color, qty) VALUES \
                            (:name, :size, :color, :qty)", \
                            name=part, size=size, color=color, qty=qty)
                print(f"New {size} {color} {part} entry created with qty {qty}.")                        

            # Update existing entry's quantity
            else:
                new_qty = onhand[0]['qty'] + qty
                if new_qty < 1:
                    db.execute("DELETE FROM parts WHERE \
                                name=:name AND size=:size AND color=:color", name=part, size=size, color=color)
                else:
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

        templates = gather_templates()
        build_production(templates)
        flash(f"Sucessfully created {qty} {size} {color} {part}")
        return redirect(f'/parts/{color}')


@app.route('/items', methods=['GET', 'POST'])
@login_required
def items():
    if request.method == 'GET':

        items = db.execute("SELECT * FROM items ORDER BY size DESC, name ASC, qty DESC")
        templates = gather_templates()

        if not 'recent_item' in session :
            session['recent_item'] = 'None'
            print("not recent item")
        print(f"loading items{session}")
        return render_template('items.html', templates=templates, items=items, recent=session['recent_item'])

    # Upon POSTing form submission
    else:
        item = request.form.get("item")
        size = request.form.get("size")
        a = request.form.get("color_a")
        b = request.form.get("color_b")
        c = request.form.get("color_c")
        qty = int(request.form.get("qty"))
        deplete = request.form.get("deplete")

        # if c == "None":
        #     c = ''

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

        print(f"SESSION:{session}")

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
        ctest = db.execute("SELECT c FROM loterias WHERE nombre=:name", name=item)

        # No c is given
        if not c:
            # But there should be a c
            if ctest[0]['c'] != '':                
                flash('Invalid entry. Color C required for this item.')
                return redirect('/items')

        # Superfulous c value is given
        else:
            if ctest[0]['c'] == '':
                flash('Invalid entry. Color C not required for this item.')
                return redirect('/items')


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
            if items_onhand:
                items_onhand = items_onhand[0]['qty']
            else:
                items_onhand = 0

            new_qty = items_onhand + qty

            if not c:
                if new_qty <= 0:
                    db.execute("DELETE FROM items WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b", \
                            item=item, size=size, a=a, b=b)
                else:
                    db.execute("UPDATE items SET qty=:qty WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b", \
                            item=item, size=size, a=a, b=b, qty=new_qty)

            else:
                if new_qty <= 0:
                    db.execute("DELETE FROM items WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b AND c_color=:c", \
                            item=item, size=size, a=a, b=b, c=c)
                else:
                    db.execute("UPDATE items SET qty=:qty WHERE name=:item AND size=:size AND a_color=:a AND b_color=:b AND c_color=:c", \
                            item=item, size=size, a=a, b=b, c=c, qty=new_qty)

        templates = gather_templates()
        build_production(templates)

        flash(f"Added to items inventory: {qty} {size} {item} ({a}, {b}, {c})")

        return redirect('/items')

# TODO ensure negative values work as well here as in /items
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

        all_projections = db.execute("SELECT * FROM projections")

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

        total = db.execute("SELECT sum(qty) FROM projections where cycle=:active", active=active)

        templates = gather_templates()

        if not 'recent_projection' in session :
            session['recent_projection'] = 'None'

        # Select projections from current cycle only
        projections = db.execute("SELECT * FROM projections WHERE cycle=:active ORDER BY size ASC, name DESC, qty DESC", active=active)
        return render_template('projections.html', templates=templates, projections=projections, current=current, cycles=cycles, total=total, recent=session['recent_projection'])

    # Upon POSTing form submission
    else:
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
        ctest = db.execute("SELECT c FROM loterias WHERE nombre=:name", name=item)

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

        templates = gather_templates()
        sku = generate_sku(templates, itemdata)
        print(f"sku:{sku}")
            
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
            db.execute("INSERT INTO projections (name, size, a_color, b_color, c_color, qty, cycle, sku) VALUES \
                        (:name, :size, :a_color, :b_color, :c_color, :qty, :cycle, :sku)", \
                        name=item, size=size, a_color=a, b_color=b, c_color=c, qty=qty, cycle=cycle, sku=sku)
            flash(f"Added to projections: {qty} {size} {item} ({a}, {b}, {c}) [{sku}]")

        # Update existing entry's quantity
        else:
            updated = projected[0]['qty'] + qty

            if not c:
                if updated < 1:
                    db.execute("DELETE FROM projections WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND cycle=:cycle", \
                        name=item, size=size, a_color=a, b_color=b, cycle=cycle)

                else:
                    db.execute("UPDATE projections SET qty=:updated WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND cycle=:cycle", \
                        updated=updated, name=item, size=size, a_color=a, b_color=b, cycle=cycle)
    
                flash(f"Added to projections: {qty} {size} {item} ({a}, {b})")

            else:
                if updated < 1:
                    db.execute("DELETE FROM projections WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color \
                        AND cycle=:cycle", \
                        name=item, size=size, a_color=a, b_color=b, c_color=c, cycle=cycle)
                else:
                    db.execute("UPDATE projections SET qty=:updated WHERE \
                        name=:name AND size=:size AND a_color=:a_color AND b_color=:b_color AND c_color=:c_color \
                        AND cycle=:cycle", \
                        updated=updated, name=item, size=size, a_color=a, b_color=b, c_color=c, cycle=cycle)

                flash(f"Added to projections: {qty} {size} {item} ({a}, {b}, {c})")

            print("Existing projection updated.")
        
        build_production(templates)

        return redirect('/projections')


@app.route('/production', methods=['GET'])
@login_required
def production():
    # (RE)BUILD PRODUCTION TABLE

    # Query for current cycle's projections
    templates = gather_templates()
    build_production(templates)
    
    flash(f"Projections (re)calculated.")
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
            if qty_onhand < 1:
                db.execute("DELETE FROM boxes WHERE name=:name", name=name)
            else:
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

        if qty == 1:
            flash(f"{qty} {name} box made.")
        else:
            flash(f"{qty} {name} boxes made.")

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
            if new_qty > 0:
                db.execute("UPDATE boxused SET qty=:qty WHERE name=:name", qty=new_qty, name=name)
            else:
                db.execute("DELETE FROM boxused WHERE name=:name", name=name)


        # Make new boxused inventory
        else:
            db.execute("INSERT INTO boxused (name, qty) VALUES (:name, :qty)", name=name, qty=qty)
    
        if qty == 1:
            flash(f"{qty} {name} box used.")
        else:
            flash(f"{qty} {name} boxes used.")

    return redirect('/parts/boxes')


@app.route('/shipping')
@login_required
def shipping():
    return render_template('shipping.html')


###### ADMINISTRATION ######
@app.route('/admin', methods=['GET'])
@login_required
def admin():

    templates = gather_templates()
    cycles = db.execute("SELECT * FROM cycles")
    users = db.execute("SELECT username, last_login FROM users ORDER BY last_login DESC")

    return render_template('admin.html', templates=templates, cycles=cycles, users=users)


@app.route('/admin/<path>', methods=['GET', 'POST'])
@login_required
def config(path):

    if request.method == 'GET':

        # Not a valid admin route
        return redirect('/')

    # On POST
    else:

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
                cycle INTEGER, \
                sku BIGINT \
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
                # Seed table with Default Event
                time = datetime.datetime.utcnow().isoformat()
                db.execute("INSERT INTO cycles (id, name, created_on, current) VALUES ('1', 'Default Event', :time, 'TRUE')", time=time)


            # EXPERIMENTAL
            # Create table: summary
            # db.execute("DROP TABLE summary")
            db.execute("CREATE TABLE IF NOT EXISTS summary ()")

            flash("Tables setup.")
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

            name = request.form.get("name")
            print(f"name:{name}")

            # Require name
            if not name:

                # Flash confirmation message
                flash(f"Name required to create new event.")

            # Make a new cycle
            else:
                # Create new Cycle
                time = datetime.datetime.utcnow().isoformat()
                db.execute("INSERT INTO cycles (name, created_on, current) VALUES (:name, :time, 'FALSE')", name=name, time=time)
                flash(f'Created new event "{name}"')
            
            return redirect('/admin')


    # Imports

        # Import event projections
        if path == 'import-event':

            event = request.form.get("event")
            templates = gather_templates()

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
    
                    total = 0
                    skipped = 0

                    values = []

                    next(csv_reader)
                    for row in csv_reader:

                        if row[2]:
                            sku = parse_sku(row[2])
                            item = generate_item(templates, sku)

                            if 'error' in item.keys():
                                flash(f"SKU Error: {item['error']}")
                                return redirect('/admin')

                            print(f"Item from production:{item}")

                        else:
                            skipped += 1

                        values.append([])
                        values[total].append(item['item'])
                        values[total].append(item['size'])
                        values[total].append(item['a'])
                        values[total].append(item['b'])
                        values[total].append(item['c'])
                        values[total].append(row[7]) # quantity
                        values[total].append(event) # event cycle number
                        values[total].append(sku['sku'])
                        print(f"values:{values}")

                        total += 1

                    values = sql_cat(values)

                    # TODO ensure no duplicate SKUs
                    db.execute("DELETE FROM projections WHERE cycle=:event", event=event)
                    db.execute(f"INSERT INTO projections (name, size, a_color, b_color, c_color, qty, cycle, sku) VALUES {values}")

                cycle_name = db.execute("SELECT name FROM cycles WHERE id=:event", event=event)

                flash(f"""Processed "{filename_user}" into database for event "{cycle_name[0]['name']}." {skipped} failures out of {total} imports.""")

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
                    filename = 'item-inventory.csv'
                    print(f"filename:{filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    with open('static/uploads/item-inventory.csv', 'r') as csvfile:

                        csv_reader = csv.reader(csvfile)
        
                        total = 0
                        skipped = 0

                        deleted = db.execute("DELETE FROM items;")

                        next(csv_reader)
                        for row in csv_reader:
                            total += 1

                            if row[0]:
                                sku = parse_sku(row[0])
                                print(f"Found:{sku}")
    
                                # TODO update to use SKU, not spreadsheet values
                                db.execute("INSERT INTO items (name, size, a_color, b_color, c_color, qty) VALUES (:name, :size, :a_color, :b_color, :c_color, :qty)",
                                                name=row[1],
                                                size=row[2],
                                                a_color=row[3],
                                                b_color=row[4],
                                                c_color=row[5],
                                                qty=row[7]
                                                )

                            else:
                                skipped += 1


                    flash(f"""Deleted {deleted} old inventory items. Processed "{filename_user}" into items inventory. {skipped}/{total} failed (no SKU).""")

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
                    filename = 'part-inventory.csv'
                    print(f"filename:{filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    with open('static/uploads/part-inventory.csv', 'r') as csvfile:

                        csv_reader = csv.reader(csvfile)
        
                        total = 0
                        skipped = 0

                        deleted = db.execute("DELETE FROM parts;")

                        next(csv_reader)
                        for row in csv_reader:
                            total += 1

                            if row[0]:

                                sku = parse_skulet(row[0])
                                print(f"Found:{sku}")

                                # TODO update to use SKU not spreadsheet values
                                db.execute("INSERT INTO parts (name, size, color, qty) VALUES (:name, :size, :color, :qty)",
                                                name=row[1],
                                                size=row[2],
                                                color=row[3],
                                                qty=row[4]
                                                )

                            else:
                                skipped += 1


                flash(f"""Deleted {deleted} old inventory items. Processed "{filename_user}" into items inventory. {skipped}/{total} failed (no SKU).""")
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


        if path == 'backup-inventory':

            type = request.form.get("type")

            if type == 'parts':
                
                cycle = request.form.get("backup-parts")
                templates = gather_templates()

                # BACKUP PARTS
                # Create new csv file
                with open('static/backups/parts_inventory.csv', 'w') as csvfile:

                    # Create writer object
                    scribe = csv.writer(csvfile)

                    # Pull all parts data
                    parts = db.execute("SELECT * FROM parts")

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

                return send_from_directory(app.config['BACKUPS'], filename='parts_inventory.csv', as_attachment=True, attachment_filename=attachname, mimetype='text/csv')

            if type == 'items':

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
                attachname = 'items_inventory_' + time + '.csv'

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

            message = ''

            if items == 'true':
                # Wipe items
                removed = db.execute("DELETE FROM items")
                message = str(removed) + " items deleted from inventory. "

            if parts == 'true':
                # Wipe parts
                removed = db.execute("DELETE FROM parts")
                message = message + str(removed) + " items deleted from inventory. "

            if boxes == 'true':
                # Wipe used boxes
                removed = db.execute("DELETE FROM boxused")
                message = message + str(removed) + " used boxes deleted from inventory. "

            if usedboxes == 'true':
                # Wipe boxes
                db.execute("DELETE FROM boxes")
                message = message + str(removed) + " boxes deleted from inventory. "

            if projections == 'true':
                # Wipe projections

                # Identify current cycle
                active = db.execute("SELECT id, name, created_on FROM cycles WHERE current='TRUE'")
                cycle = active[0]['id']

                removed = db.execute("DELETE FROM projections where cycle=:cycle", cycle=cycle)
                message = message + str(removed) + " items removed from current event projections.\n"

                removed = db.execute("DELETE FROM production")
                message = message + str(removed) + " parts removed from current event laser queue.\n"

                removed = db.execute("DELETE FROM boxprod")
                message = message + str(removed) + " boxes removed from current event laser queue.\n"

            flash(message)
            return redirect("/admin")


        if path == 'delete-event':

            id = request.form.get("cycle-id")
            name = request.form.get("cycle-name")

            print(id, name)

            if int(id) != 1:
                deleted = db.execute("SELECT * FROM cycles WHERE id=:id", id=id)
                db.execute("DELETE from CYCLES where id=:id", id=id)
                db.execute("UPDATE cycles SET current='TRUE' WHERE id=1")
                projections = db.execute("DELETE FROM projections WHERE cycle=:id", id=id)

                flash(f"""Event cycle "{deleted[0]['name']}" and {projections} associated projections deleted.""")
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

            templates = gather_templates()
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
        if not db.execute("SELECT username FROM users WHERE username LIKE (?)", username):

            # Add the username
            time = datetime.datetime.utcnow().isoformat()
            db.execute("INSERT INTO users (username, password, created_on) VALUES (:username, :hashedpass, :time)",
                        username=username, hashedpass=hashedpass, time=time)
            return redirect("/")

        else:
            flash("Username invalid or already taken.")
            return redirect('/register')


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):

            flash("Username required.")
            return redirect('/login')

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Password required.")
            return redirect('/login')

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists
        if len(rows) != 1:
            flash("Username not found.")
            return redirect('/login')

        # Ensure username exists and password is correct
        if not check_password_hash(rows[0]["password"], request.form.get("password")):
            flash("Incorrect password.")
            return redirect('/login')

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Update "last_login"
        time = datetime.datetime.utcnow().isoformat()
        db.execute("UPDATE users SET last_login=:time WHERE id=:id", time=time, id=session["user_id"])

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
