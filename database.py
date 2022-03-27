import os
import csv
import psycopg2
import psycopg2.extras
import datetime

from dotenv import load_dotenv
load_dotenv()


# # Setup PostgreSQL database connection
# conn = ''
# try:
#     # Testing
#     if int(os.getenv('FLASK_DEBUG')) == 1: # Testing DB until migration
#         print("Connecting to Turkosaurus database ...", end="")
#         conn = psycopg2.connect(os.getenv('HEROKU_POSTGRESQL_BLUE_URL'))
#         print("connected.")
#     # Production
#     else:
#         print("Connecting to PRODUCTION environment...", end="")
# except:
#     print("unable to connect.")
#     conn = "Unable to connect."

# FUNCTIONS #

def tupleToDict(tuple_in):
    result = []
    for row in tuple_in:
        result.append(dict(row._asdict()))
    return result

def quick_execute_dict(conn, query): # TODO delete if unused
    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
    cur.execute(f"{query}")
    result = tupleToDict(cur.fetchall())
    conn.commit()
    cur.close()

    return result

def gather_templates(conn):

    # Gather template data
    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

    cur.execute("SELECT * FROM nail_loterias ORDER BY SKU ASC")
    loterias = tupleToDict(cur.fetchall())

    cur.execute("SELECT * FROM nail_shirts")
    shirts = tupleToDict(cur.fetchall())

    cur.execute("SELECT * FROM nail_colors")
    colors = tupleToDict(cur.fetchall())

    cur.execute("SELECT * FROM nail_sizes")
    sizes = tupleToDict(cur.fetchall())

    cur.execute("SELECT * FROM nail_types")
    types = tupleToDict(cur.fetchall())

    response = {
        'loterias': loterias,
        'shirts': shirts,
        'colors': colors,
        'sizes': sizes,
        'types': types
    }

    conn.commit()
    cur.close()

    return response

def setup_loterias(conn):

    with open('static/uploads/loterias.csv', 'r') as csvfile:

        print('Reading loterias.csv...')
        csv_reader = csv.reader(csvfile)

        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS nail_loterias ( \
            nombre VARCHAR (255) NOT NULL, \
            a VARCHAR (255), \
            b VARCHAR (255), \
            c VARCHAR (255), \
            backs VARCHAR (255), \
            sku INTEGER \
            )")

        cur.execute("DELETE from nail_loterias")

        next(csv_reader)
        counter = 0
        for row in csv_reader:
            counter += 1
            cur.execute("INSERT INTO nail_loterias (sku, nombre, a, b, c, backs) VALUES (%s, %s, %s, %s, %s, %s)", \
                            (row[0], row[1], row[2], row[3], row[4], row[5]))

        conn.commit()
        cur.close()
        return counter

def initialize_database(conn):
    print("Creating new tables...")
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS \
        nail_colors, \
        nail_sizes, \
        nail_lotierias, \
        nail_shirts, \
        nail_types, \
        nail_users, \
        nail_parts, \
        nail_items, \
        nail_boxes, \
        nail_boxprod, \
        nail_boxused, \
        nail_projections, \
        nail_production, \
        nail_cycles \
        ")
        # nail_users, \

    try:
        setup_loterias(conn)
        print("Loterias setup from loterias.csv")
    except Exception as e:
        print("Error writing to database from loterias.csv. File may be missing.")
        print(e)


    # Users
    cur.execute("CREATE TABLE IF NOT EXISTS nail_users ( \
        id SERIAL NOT NULL, \
        username VARCHAR ( 255 ) UNIQUE NOT NULL, \
        password VARCHAR ( 255 ) NOT NULL, \
        created_on TIMESTAMP, \
        last_login TIMESTAMP \
        )")


    # Colors
    cur.execute("CREATE TABLE IF NOT EXISTS nail_colors ( \
        sku SERIAL NOT NULL, \
        name VARCHAR ( 255 ), \
        emoji VARCHAR ( 255 ), \
        cssname VARCHAR ( 255 ) \
        )")

    colors = [
        ['black', '⬛', 'black'], 
        ['red', '🟥', 'red'], 
        ['TQ', '🟦', 'turquoise'], 
        ['yellow', '🟨', 'yellow'], 
        ['green', '🟩', 'green'], 
        ['purple', '🟪', 'purple'], 
        ['white', '⬜', 'white'],
        ['grey', '🔲', 'grey'],
        ['gold', '🥇', 'gold'],
        ['rose', '🌹', 'pink']        
        ]

    cur.execute("SELECT * FROM nail_colors")
    color_data = cur.fetchall()
    if not color_data:
        for i in range(len(colors)):
            cur.execute("INSERT INTO nail_colors (sku, name, emoji, cssname) VALUES (%s, %s, %s, %s)", ((i+1), colors[i][0], colors[i][1], colors[i][2]))

    # Sizes
    cur.execute("CREATE TABLE IF NOT EXISTS nail_sizes ( \
        sku INTEGER NOT NULL, \
        shortname VARCHAR ( 255 ), \
        longname VARCHAR ( 255 ) \
        )")

    cur.execute("SELECT * FROM nail_sizes")
    size_data = cur.fetchall()
    if not size_data:
        sizes = [['S', 'small'], ['M', 'medium'], ['L', 'large'], ['XL', 'XL'], ['2XL','2XL']]
        for i in range(len(sizes)):
            cur.execute("INSERT INTO nail_sizes (sku, shortname, longname) VALUES (%s, %s, %s)", ((i+1), sizes[i][0] , sizes[i][1]))


    # Create table: recent
    # cur.execute("CREATE TABLE IF NOT EXISTS nail_recent ( \
    #     user_id INTEGER, \
    #     projection VARCHAR ( 255 ), \
    #     item VARCHAR ( 255 ), \
    #     part VARCHAR ( 255 ), \
    #     PRIMARY KEY(user_id), \
    #     CONSTRAINT
    # )")


    # Parts
    cur.execute("CREATE TABLE IF NOT EXISTS nail_parts ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        color VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Items
    cur.execute("CREATE TABLE IF NOT EXISTS nail_items ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        a_color VARCHAR ( 255 ), \
        b_color VARCHAR ( 255 ), \
        c_color VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Types
    cur.execute("CREATE TABLE IF NOT EXISTS nail_types ( \
        name VARCHAR ( 255 ), \
        sku INTEGER \
        )")

    types = [
        ['Laser Cut', '0'],
        ['Tee Shirt', '1'],
        ['Tank Top', '2'],
        ['Hoodie', '3'],
        ['Screen Print', '10'],
        ['Greeting Card', '11'] 
        ]

    cur.execute("SELECT * FROM nail_types")
    types_data = cur.fetchall()
    if not types_data:
        for i in range(len(types)):
            cur.execute("INSERT INTO nail_types (name, sku) VALUES (%s, %s)", (types[i][0], types[i][1]))

    # Shirts
    # Reformat these tables to be more relational with types, depending on business needs
    cur.execute("CREATE TABLE IF NOT EXISTS nail_shirts ( \
        nombre VARCHAR ( 255 ) NOT NULL, \
        a VARCHAR ( 255 ), \
        b VARCHAR ( 255 ), \
        c VARCHAR ( 255 ), \
        backs VARCHAR ( 255 ), \
        sku INTEGER \
        )")

    shirts = [
        ['ReSister', '55']
    ]
    cur.execute("SELECT * FROM nail_shirts")
    shirts_data = cur.fetchall()
    if not shirts_data:
        for i in range(len(shirts)):
            cur.execute("INSERT INTO nail_shirts (nombre, sku) VALUES (%s, %s)", (shirts[i][0], shirts[i][1]))


    # Create table: boxes
    cur.execute("CREATE TABLE IF NOT EXISTS nail_boxes ( \
        name VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Create table: boxprod
    cur.execute("CREATE TABLE IF NOT EXISTS nail_boxprod ( \
        name VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Create table: boxused
    cur.execute("CREATE TABLE IF NOT EXISTS nail_boxused ( \
        name VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Create table: projections
    cur.execute("CREATE TABLE IF NOT EXISTS nail_projections ( \
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
    cur.execute("CREATE TABLE IF NOT EXISTS nail_production ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        color VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Create table: cycles
    cur.execute("CREATE TABLE IF NOT EXISTS nail_cycles ( \
        id SERIAL NOT NULL, \
        name VARCHAR (255), \
        created_on TIMESTAMP, \
        current BOOL \
        )")

    # If empty cycles table
    cur.execute("SELECT * FROM nail_cycles")
    event_data = cur.fetchall()
    if not event_data:
        # Seed table with Default Event
        time = datetime.datetime.utcnow().isoformat()
        cur.execute("INSERT INTO nail_cycles (id, name, created_on, current) VALUES ('1', 'Default Event', %(time)s, 'TRUE')", {'time':time})

    conn.commit()
    cur.close()

def restore_items(conn):
    from helpers import parse_sku
    cur = conn.cursor()

    with open('static/uploads/item-inventory.csv', 'r') as csvfile:

        csv_reader = csv.reader(csvfile)

        total = 0
        skipped = 0

        deleted = cur.execute("DELETE FROM nail_items RETURNING *;") # TODO test returning

        next(csv_reader)
        for row in csv_reader:
            total += 1

            if row[0]:
                sku = parse_sku(row[0])
                print(f"Found:{sku}")

                # TODO update to use SKU, not spreadsheet values
                cur.execute("INSERT INTO nail_items (name, size, a_color, b_color, c_color, qty) VALUES \
                (%s, %s, %s, %s, %s, %s)", (row[1], row[2], row[3], row[4], row[5], row[7]))

            else:
                skipped += 1

    conn.commit()
    cur.close()

    results = {
        "deleted":deleted,
        "skipped":skipped,
        "total":total
    }
    return results


def restore_parts(conn):
    from helpers import parse_skulet
    cur = conn.cursor()

    with open('static/uploads/part-inventory.csv', 'r') as csvfile:

        csv_reader = csv.reader(csvfile)

        total = 0
        skipped = 0

        deleted = cur.execute("DELETE FROM nail_parts RETURNING *;") # TODO test returning

        next(csv_reader)
        for row in csv_reader:
            total += 1

            if row[0]:

                sku = parse_skulet(row[0])
                print(f"Found:{sku}")

                # TODO update to use SKU not spreadsheet values
                cur.execute("INSERT INTO nail_parts (name, size, color, qty) VALUES \
                    (%s, %s, %s, %s)", (row[1], row[2], row[3], row[4]))

            else:
                skipped += 1

    conn.commit()
    cur.close()

    results = {
        "deleted":deleted,
        "skipped":skipped,
        "total":total
    }
    return results


