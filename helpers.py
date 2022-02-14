#pseudocode to describe core function of CS50 python library
# https://github.com/cs50/python-cs50/blob/main/src/cs50/sql.py

def execute(query, *args)

    cur = conn.cursor()
    cur.execute(f'"{query}", {args}')
    conn.commit()
    cur.close
    return 0

def append_args(args):
    arg = ''
    for arg in args:
        arg = f""
