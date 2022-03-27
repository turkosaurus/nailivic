import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from database import tupleToDict
load_dotenv()

# Configure Heroku Postgres database
# db = SQL(os.getenv('DATABASE_URL'))

def sql_cat(lists):
    # Takes list of lists and converts them into SQL compatible string concatenations
    # Which is a terrible thing that should never be done, but is forced by lack of INSERTMANY in CS50
    # and is mitigated by only being applied on internal data, and escaping some characters
    # TODO convert all SQL calls to psychopg3

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




def build_production(conn, templates, db):

    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

    cur.execute("SELECT * FROM nail_projections WHERE cycle=(SELECT id FROM nail_cycles WHERE current='TRUE')")
    projections = tupleToDict(cur.fetchall())
    
    cur.execute("SELECT * FROM nail_items")
    items = tupleToDict(cur.fetchall())

    cur.execute("SELECT * FROM nail_parts")    
    parts = tupleToDict(cur.fetchall())
    
    cur.execute("SELECT * FROM nail_boxes UNION SELECT * FROM nail_boxused")
    boxes = tupleToDict(cur.fetchall())

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
                print(f"Matched {q[0]} {q[1]} {q[2]}")
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
                print(f"---")

            # else:
            #     print(f"{part}")
            #     print(f"UNMATCHED: {part['name']} {part['size']} {part['color']}")
            #     print(f"UNMATCHED {q[0]} {q[1]} {q[2]}")


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
    # box_queue = sql_cat(box_queue)
    print(f"after:{box_queue}")

    # print(f"String:{box_queue}")

    # parts
    print("Parts List:")
    # for row in queue:
        # print(row)

    # queue = sql_cat(queue)
    # print(f"String:{queue}")

    # queue = tuplefy(queue)
    # print(f"Tuples:{queue}")

    box_added = 0
    part_added = 0

    # Wipe Box Produciton
    cur.execute("DELETE FROM nail_boxprod")
    print(f"box_queue:{box_queue}")

    # New Box Production
    if box_queue:
        print(box_queue)
        query = "INSERT INTO nail_boxprod (name, qty) VALUES %s"
        psycopg2.extras.execute_values (
            cur, query, box_queue, template=None, page_size=100 
        )
    
    # Wipe production
    cur.execute("DELETE FROM nail_production")

    # New Part Production
    if queue:
        query = "INSERT INTO nail_production (name, qty) VALUES %s"
        psycopg2.extras.execute_values (
            cur, query, queue, template=None, page_size=100 
        )

    data = ((1, 2), (3, 4), (5, 6), (7, 8))
    query = "INSERT INTO foo (a, b) VALUES %s"
    psycopg2.extras.execute_values (
        cur, query, data, template=None, page_size=100 
    )

    conn.commit()
    cur.close()

    # tmp = {
    #     'projections': total_projections,
    #     'boxes': box_added,
    #     'parts': part_added
    # }

    # Handle divide by zero error
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
        



# #pseudocode to describe core function of CS50 python library
# # https://github.com/cs50/python-cs50/blob/main/src/cs50/sql.py

# def execute(query, *args):

#     cur = conn.cursor()
#     cur.execute(f'"{query}", {args}')
#     conn.commit()
#     cur.close
#     return 0

# def append_args(args):
#     arg = ''
#     for arg in args:
#         arg = f""
