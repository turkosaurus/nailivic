import os
import csv
import psycopg2
import datetime
from dotenv import load_dotenv
load_dotenv()


# Setup PostgreSQL database connection
conn = ''
try:
    # Testing
    if int(os.getenv('FLASK_DEBUG')) == 1: # Testing DB until migration
        print("Connecting to Turkosaurus database ...", end="")
        conn = psycopg2.connect(os.getenv('HEROKU_POSTGRESQL_BLUE_URL'))
        print("connected.")
    # Production
    else:
        print("Connecting to PRODUCTION environment...", end="")
except:
    print("unable to connect.")



def setup_loterias():

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


def initialize_database():
    print("Creating new tables...")
    cur = conn.cursor()

    # cur.execute("DROP TABLE \
        # nail_users, \
        # nail_colors, \
        # nail_sizes, \
        # nail_parts, \
        # nail_items, \
        # nail_boxes, \
        # nail_boxprod, \
        # nail_boxused, \
        # nail_projections, \
        # nail_production, \
        # nail_cycles \
        # ")

    try:
        setup_loterias()
        print("Loterias setup from loterias.csv")
    except Exception as e:
        print("Error writing to database from loterias.csv. File may be missing.")
        print(e)


    # Create table: users
    cur.execute("CREATE TABLE IF NOT EXISTS nail_users ( \
        id SERIAL NOT NULL, \
        username VARCHAR ( 255 ) UNIQUE NOT NULL, \
        password VARCHAR ( 255 ) NOT NULL, \
        created_on TIMESTAMP, \
        last_login TIMESTAMP \
        )")


    # Create table: colors
    cur.execute("CREATE TABLE IF NOT EXISTS nail_colors ( \
        sku INTEGER NOT NULL, \
        name VARCHAR ( 255 ), \
        emoji VARCHAR ( 255 ) \
        )")

    colors = [['black', '⬛'],['red', '🟥'], ['TQ', '🟦'], ['yellow', '🟨'], ['green', '🟩'], ['purple', '🟪'], ['white', '⬜']]
    for i in range(len(colors)):
        cur.execute("INSERT INTO nail_colors (sku, name, emoji) VALUES (%s, %s, %s)", ((i+1), colors[i][0], colors[i][1]))


    # Create table: sizes
    cur.execute("CREATE TABLE IF NOT EXISTS nail_sizes ( \
        sku INTEGER NOT NULL, \
        shortname VARCHAR ( 255 ), \
        longname VARCHAR ( 255 ) \
        )")

    sizes = [['S', 'small'], ['M', 'medium'], ['L', 'large']]
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


    # Create table: parts
    cur.execute("CREATE TABLE IF NOT EXISTS nail_parts ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        color VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    # Create table: items
    cur.execute("CREATE TABLE IF NOT EXISTS nail_items ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        a_color VARCHAR ( 255 ), \
        b_color VARCHAR ( 255 ), \
        c_color VARCHAR ( 255 ), \
        qty INTEGER \
        )")

    cur.execute("CREATE TABLE IF NOT EXISTS nail_types ( \
        name VARCHAR ( 255 ), \
        sku INTEGER \
        )")

    cur.execute("CREATE TABLE IF NOT EXISTS nail_shirts ( \
        name VARCHAR ( 255 ) NOT NULL, \
        size VARCHAR ( 255 ) NOT NULL, \
        a VARCHAR ( 255 ), \
        b VARCHAR ( 255 ), \
        c VARCHAR ( 255 ), \
        backs VARCHAR ( 255 ), \
        sku INTEGER \
        )")

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
    data = cur.execute("SELECT * FROM nail_cycles")
    if not data:
        # Seed table with Default Event
        time = datetime.datetime.utcnow().isoformat()
        cur.execute("INSERT INTO nail_cycles (id, name, created_on, current) VALUES ('1', 'Default Event', %(time)s, 'TRUE')", {'time':time})

    conn.commit()
    cur.close()

