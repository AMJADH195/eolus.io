from . import pg_connection_manager as pg
from .config import config
from datetime import datetime, timedelta, tzinfo, time


def log(text, level, indentLevel=0, remote=False, model=''):

    if level not in config["logLevels"]:
        return

    timestamp = datetime.utcnow()
    time_str = timestamp.strftime("%H:%M:%S")
    indents = ""

    for i in range(0, indentLevel):
        indents += "   "

    print(f"[{level}\t| {time_str}] {indents}{text}")

    if remote:
        try:
            pg.ConnectionPool.curr.execute(
                "INSERT INTO eolus4.log (model, level, timestamp, agent, message) VALUES (%s, %s, %s, %s, %s)", (model, level, timestamp, '0', text))
            pg.ConnectionPool.conn.commit()
        except:
            print("Wasn't logged remotely :(")
            pg.reset()


def print_line():
    print("-----------------")


def say_hello():
    print('''
    -------------------------------------------

                        '||                   
          ....    ...    ||  ... ...   ....   
        .|...|| .|  '|.  ||   ||  ||  ||. '   
        ||      ||   ||  ||   ||  ||  . '|..
         '|...'  '|..|' .||.  '|..'|. |'..|'
 
          eolus weather technologies, ltd.
                    version 4
    -------------------------------------------
    ''')
