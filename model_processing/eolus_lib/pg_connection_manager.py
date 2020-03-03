from .logger import log
from .config import config, models, levelMaps
from datetime import datetime
import psycopg2
from psycopg2 import pool
import os

pid = str(os.getpid())


class ConnectionPool:
    __instance = None
    __pool = None

    @staticmethod
    def connect():
        if ConnectionPool.__instance == None:
            ConnectionPool()
        conn = ConnectionPool.__pool.getconn()
        curr = conn.cursor()
        return conn, curr

    @staticmethod
    def close(conn, curr):
        try:
            curr.close()
            ConnectionPool.__pool.putconn(conn)
        except:
            log("Couldn't close pool", "DEBUG")

    @staticmethod
    def kill():
        ConnectionPool.__pool.closeall()

    def __init__(self):
        if ConnectionPool.__instance == None:
            ConnectionPool.__instance = self

        log("Making new pg connection pool...", "NOTICE")

        ConnectionPool.__pool = psycopg2.pool.ThreadedConnectionPool(1, 50,
                                                                     host=config["postgres"]["host"],
                                                                     port=5432,
                                                                     dbname=config["postgres"]["db"],
                                                                     user=config["postgres"]["user"],
                                                                     sslmode="require")


def add_agent():
    try:
        conn, curr = ConnectionPool.connect()
        curr.execute(
            "INSERT INTO eolus4.agents (pid, start_time) VALUES (%s, %s)", (pid, datetime.utcnow()))
        conn.commit()
        ConnectionPool.close(conn, curr)
    except Exception as e:
        pg.ConnectionPool.close(conn, curr)
        log("Couldn't add agent.", "ERROR")
        log(repr(e), "ERROR", indentLevel=1, remote=True)
        return False
    return True


def remove_agent():
    log("Removing agent " + pid, "DEBUG")
    try:
        conn, curr = ConnectionPool.connect()
        curr.execute(
            "DELETE FROM eolus4.agents WHERE pid = %s", (pid,))
        conn.commit()
        ConnectionPool.close(conn, curr)
    except:
        ConnectionPool.close(conn, curr)
        log("Couldn't remove agent.", "ERROR", remote=True)
        return False
    return True


def can_do_work():
    try:
        conn, curr = ConnectionPool.connect()
        curr.execute("SELECT COUNT(*) FROM eolus4.agents")
        conn.commit()
        result = curr.fetchone()
        ConnectionPool.close(conn, curr)
        return result[0] == 0
    except Exception as e:
        ConnectionPool.close(conn, curr)
        log("Couldn't get agent count.", "ERROR", remote=True)
        log(repr(e), "ERROR", indentLevel=1, remote=True)
        return False


def connect():
    try:
        log("Connecting to database [" +
            config["postgres"]["host"] + "]", "INFO")

        ConnectionPool()

        return True

    except psycopg2.Error as e:
        log("Could not connect to postgres.", "ERROR")
        print(str(e))
        print(str(e.pgerror))
        return False


def clean():
    try:
        conn, curr = ConnectionPool.connect()
        curr.execute(
            "DELETE FROM eolus4.log WHERE timestamp < now() - interval '" + config["retentionDays"] + " days'")
        conn.commit()
        curr.execute(
            "DELETE FROM eolus4.run_status WHERE timestamp < now() - interval '" + config["retentionDays"] + " days'")
        conn.commit()
        ConnectionPool.close(conn, curr)
    except:
        ConnectionPool.close(conn, curr)
        log(f"· Couldn't delete old logs.",
            "WARN", indentLevel=0, remote=True)
