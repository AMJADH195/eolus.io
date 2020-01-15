from eolus_lib.config import config
from eolus_lib.logger import log
import eolus_lib.pg_connection_manager as pg

import os


def clean():
    retentionDays = str(config["retentionDays"])
    log(f"· Deleting rasters from {config['mapfileDir']} older than {retentionDays} days.",
        "DEBUG", indentLevel=0)
    try:
        os.system(
            f'find {config["mapfileDir"]}/*/* -mtime +' + retentionDays + ' -exec rm {} \;')
        os.system(f'find {config["tempDir"]}/* -mtime +' +
                  retentionDays + ' -exec rm {} \;')
    except:
        log(f"· Couldn't delete old rasters from {config['mapfileDir']}.",
            "WARN", indentLevel=0, remote=True)

    log(f"· Cleaning logs older than {retentionDays} days.",
        "DEBUG", indentLevel=0)
    try:
        pg.clean()
    except:
        pg.reset()
        log(f"· Couldn't delete old logs.",
            "WARN", indentLevel=0, remote=True)
