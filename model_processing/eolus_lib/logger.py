from . import pg_connection_manager as pg
from datetime import datetime, timedelta, tzinfo, time


def log(text, level, indentLevel=0, remote=False, model=''):
    timestamp = datetime.utcnow()
    timeStr = timestamp.strftime("%H:%M:%S")
    indents = ""

    for i in range(0, indentLevel):
        indents += "   "

    print(f"[{level}\t| {timeStr}] {indents}{text}")

    if remote:
        try:
            pg.ConnectionPool.curr.execute(
                "INSERT INTO eolus3.log (model, level, timestamp, agent, message) VALUES (%s, %s, %s, %s, %s)", (model, level, timestamp, '0', text))
            pg.ConnectionPool.conn.commit()
        except:
            print("Wasn't logged remotely :(")
            pg.reset()


def print_line():
    print("-----------------")


def say_hello():
    print('''
    ----------------------------------------
     OOOO   OOO    O     O  O    OOO   OOO
     O     O   O   O     O  O   O         O
     OO    O - O   O     O  O    OO     OO
     O     O   O   O     O  O      O      O
     OOOO   OOO    OOOO   OOO   OOO    OOO
    ----------------------------------------
    ''')
