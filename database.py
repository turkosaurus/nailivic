# from asyncio import gather
import os
import csv
import psycopg2
import psycopg2.extras
import datetime

from dotenv import load_dotenv
load_dotenv()

# FUNCTIONS #

def tupleToDict(tuple_in):
    result = []
    for row in tuple_in:
        result.append(dict(row._asdict()))
    return result


def fetchDict(cur):
    try:
        result = tupleToDict(cur.fetchall())
        if int(os.getenv('FLASK_DEBUG')) == 1: # Testing DB until migration
            print(f"fetchDict returning:\n{result}")
        return result
    except Exception as e:
        print(f"Fetch error {e}")
        return None


def execDict(conn, query):
    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
    if query.split[0] != "SELECT":
        err = "Usage error, execDict query must be SELECT"
        print(err)
        return err
    cur.execute(f"{query}")
    result = fetchDict(cur)
    print(f"execDict returning:\n{result}")
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

        print('reading loterias.csv...', end='')
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


def drop_tables(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS \
        nail_colors, \
        nail_sizes, \
        nail_lotierias, \
        nail_shirts, \
        nail_types, \
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
    conn.commit()
    cur.close


def initialize_database(conn):
    print("initialize_database()...", end='')
    cur = conn.cursor()

    try:
        setup_loterias(conn)
        print("loterias setup.")
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
        sku INTEGER, \
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
        id SERIAL UNIQUE NOT NULL, \
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
        cur.execute("INSERT INTO nail_cycles (name, created_on, current) VALUES ('Default Event', %s, 'TRUE')", (time,))

    conn.commit()
    cur.close()


def migrate_users(conn):

    from cs50 import SQL
    # Configure Heroku Postgres database
    db = SQL(os.getenv('DATABASE_URL'))

    # Migrates users from CS50 "db" to psycopg2 "conn"
    try:
        # get old users
        users = db.execute("SELECT * FROM users")
        users_formatted = []
        i = 0
        for user in users:
            users_formatted.append([])
            for col in user.values():
                users_formatted[i].append(col)
            i += 1

        # add new users
        cur = conn.cursor()
        query = "INSERT INTO nail_users (id, username, password, created_on, last_login) VALUES %s"
        psycopg2.extras.execute_values (
            cur, query, users_formatted, template=None, page_size=100 
        )
        conn.commit()
        cur.close()
        status = f"Migrated {i} users."

    except Exception as e:
        status = f"Unable to migrate. {e}"
    
    return status


def migrate_events(conn):

    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

    # get old cycles
    cur.execute("SELECT name, created_on FROM nail_cycles")
    cycles = fetchDict(cur)
    cycles_formatted = []
    i = 0
    for cycle in cycles:
        cycles_formatted.append([])
        for col in cycle.values():
            cycles_formatted[i].append(col)
        i += 1

    # get old projections
    cur.execute("SELECT * FROM nail_projections")
    projections = fetchDict(cur)
    projections_formatted = []
    i = 0
    for projection in projections:
        projections_formatted.append([])
        for col in projection.values():
            projections_formatted[i].append(col)
        i += 1

    # add new cycles
    print("cycles formatted")
    print(cycles_formatted)
    query = "INSERT INTO nail_cycles (name, created_on) VALUES %s"
    psycopg2.extras.execute_values (
        cur, query, cycles_formatted, template=None, page_size=100 
    )
    status = f"Migrated {i} cycles."

    # add new projections
    print("projetions formatted")
    print(projections_formatted)
    query = "INSERT INTO nail_projections (name, size, a_color, b_color, c_color, qty, cycle, sku) VALUES %s"
    psycopg2.extras.execute_values (
        cur, query, projections_formatted, template=None, page_size=100 
    )
    conn.commit()
    cur.close()
    status = f"Migrated {i} projections."
    
    return status


def restore_items(conn):
    from helpers import parse_sku
    cur = conn.cursor()

    with open('static/uploads/item-inventory.csv', 'r') as csvfile:

        csv_reader = csv.reader(csvfile)

        total = 0
        skipped = 0

        deleted = cur.execute("DELETE FROM nail_items RETURNING *;") # TODO test returning here and on restore_parts()
        print(f"TEST for the RETURNING sql word, deleted=\n{deleted}")

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


def restore_event(conn, event):
    from helpers import parse_sku, generate_item

    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

    templates = gather_templates(conn)

    with open('static/uploads/event.csv', 'r') as csvfile:

        csv_reader = csv.reader(csvfile)

        total = 0
        added = 0
        skipped = 0
        errors = ''
        err_lines = []

        values = []

        next(csv_reader)
        for row in csv_reader:
            total += 1

            # SKU exists
            if row[2]:
                sku = parse_sku(row[2])
                item = generate_item(templates, sku)

                if 'error' in item.keys():
                    skipped += 1
                    err_lines.append(total + 1)
                    errors = f"{item['error']}"
                    continue

                    # flash(f"SKU Error: {item['error']}")
                    # return redirect('/admin') # harsh error handling

                print(f"Item from production:{item}")

            else:
                skipped += 1
                err_lines.append(total + 1)

            values.append([])
            values[added].append(item['item'])
            values[added].append(item['size'])
            values[added].append(item['a'])
            values[added].append(item['b'])
            values[added].append(item['c'])
            values[added].append(row[7]) # quantity
            values[added].append(event) # event cycle number
            values[added].append(sku['sku'])
            print(f"values:{values}")
            added += 1

        # values = sql_cat(values) # TODO delete this once functional with

        # TODO ensure no duplicate SKUs
        cur.execute("DELETE FROM nail_projections WHERE cycle=%s", (event,))
        query = "INSERT INTO nail_projections (name, size, a_color, b_color, c_color, qty, cycle, sku) VALUES %s"
        psycopg2.extras.execute_values (
            cur, query, values, template=None, page_size=100 
        )

        cur.execute("SELECT name FROM nail_cycles WHERE id=%s", (event,))
        cycle_name = fetchDict(cur)

        conn.commit()
        cur.close()

        results = {
            'added':added,
            'total':total,
            'skipped':skipped,
            'err_lines':err_lines,
            'errors':errors,
            'cycle_name':cycle_name
        }

    return results

