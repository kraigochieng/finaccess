STATA_TO_POSTGRESQL = {
    # Numeric types (use smallest possible)
    "byte": "SMALLINT",  # 2 bytes
    "int": "INTEGER",  # 4 bytes
    "long": "BIGINT",  # 8 bytes
    "float": "REAL",  # 4 bytes
    "double": "DOUBLE PRECISION",  # 8 bytes
    # Fixed-length strings → exact VARCHAR(n)
    "str1": "VARCHAR(1)",
    "str4": "VARCHAR(4)",
    "str6": "VARCHAR(6)",
    "str7": "VARCHAR(7)",
    "str8": "VARCHAR(8)",
    "str11": "VARCHAR(11)",
    "str12": "VARCHAR(12)",
    "str13": "VARCHAR(13)",
    "str14": "VARCHAR(14)",
    "str15": "VARCHAR(15)",
    "str16": "VARCHAR(16)",
    "str17": "VARCHAR(17)",
    "str18": "VARCHAR(18)",
    "str19": "VARCHAR(19)",
    "str20": "VARCHAR(20)",
    "str21": "VARCHAR(21)",
    "str22": "VARCHAR(22)",
    "str24": "VARCHAR(24)",
    "str25": "VARCHAR(25)",
    "str26": "VARCHAR(26)",
    "str27": "VARCHAR(27)",
    "str28": "VARCHAR(28)",
    "str29": "VARCHAR(29)",
    "str30": "VARCHAR(30)",
    "str32": "VARCHAR(32)",
    "str99": "VARCHAR(99)",
    # Long / variable strings
    "strL": "TEXT",  # Stata long string (can be huge)
    "strl": "TEXT",  # lowercase variant
}
