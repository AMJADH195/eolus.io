from eolus_lib.logger import log
from eolus_lib.config import config, models, levelMaps
import psycopg2
import os

pid = str(os.getpid())


class ConnectionPool:
    conn = None
    curr = None


def reset():
    if not ConnectionPool.conn.closed:
        ConnectionPool.conn.cancel()
        ConnectionPool.conn.reset()


def close():
    ConnectionPool.curr.close()
    ConnectionPool.conn.close()


def add_agent():
    try:
        eolus_lib.pg_connection_manager.curr.execute(
            "INSERT INTO eolus3.agents (pid, start_time) VALUES (%s, %s)", (pid, datetime.utcnow()))
        eolus_lib.pg_connection_manager.conn.commit()
        return True
    except:
        log("Couldn't add agent.", "ERROR")
        return False


def remove_agent():
    log("Removing agent " + pid, "DEBUG")
    try:
        ConnectionPool.curr.execute(
            "DELETE FROM eolus3.agents WHERE pid = %s", (pid,))
        ConnectionPool.conn.commit()
        return True
    except:
        reset()
        return False


def can_do_work():
    try:
        ConnectionPool.curr.execute("SELECT COUNT(*) FROM eolus3.agents")
        ConnectionPool.conn.commit()
        result = ConnectionPool.curr.fetchone()
        return result[0] == 0
    except:
        reset()
        log("Couldn't get agent count.", "ERROR", remote=True)
        return False


def connect():
    try:
        log("Connecting to database [" +
            config["postgres"]["host"] + "]", "INFO")

        ConnectionPool.conn = psycopg2.connect(
            host=config["postgres"]["host"],
            port=5432,
            dbname=config["postgres"]["db"],
            user=config["postgres"]["user"],
            sslmode="require")

        ConnectionPool.curr = ConnectionPool.conn.cursor()
        return True

    except psycopg2.Error as e:
        log("Could not connect to postgres.", "ERROR")
        print(str(e))
        print(str(e.pgerror))
        return False


def clean():
    ConnectionPool.curr.execute(
        "DELETE FROM eolus3.log WHERE timestamp < now() - interval '" + config["retentionDays"] + " days'")
    ConnectionPool.conn.commit()
    ConnectionPool.curr.execute(
        "DELETE FROM eolus3.run_status WHERE timestamp < now() - interval '" + config["retentionDays"]  + " days'")
    ConnectionPool.conn.commit()
