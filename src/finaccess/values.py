import logging
import re
from pathlib import Path

import pandas as pd

from finaccess.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

path = Path("2024_Finaccess_Publicdata_values.txt")

text = path.read_text()

current_vallab = None

rows = []

for line in text.splitlines():
    line = line.replace('"', "")  # Removing
    line = line.strip()

    # When the line ends with a semicolonm, it is a title else it is a value
    if line.endswith(":"):
        current_vallab = line[:-1]  # Remove semicolon

        # logger.debug(f"Current Vallab: {line}")

    else:
        code, value = re.split(r"[- ]", line, maxsplit=1)

        # logger.debug(f"Row: {current_vallab} | {code} | {value}")

        rows.append({"vallab": current_vallab, "code": code, "value": value})


df = pd.DataFrame(rows)

# Export to CSV
df.to_csv("2024_Finaccess_Publicdata_values_processed.csv", index=False)
