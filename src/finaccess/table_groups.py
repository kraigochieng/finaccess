def get_table_groups(columns: list[str]) -> dict[str, list[str]]:
    # === MAP EVERY VARIABLE TO ITS OFFICIAL QUESTIONNAIRE SECTION ===
    return {
        # Section A – Household & Respondent
        "A": [col for col in columns if col.startswith(("A0", "A1", "A2", "A9"))]
        + [
            "county",
            "Z1",
            "RESPONDENT",
            "Sex",
            "Age",
            "NHM",
            "FHH_Spouse",
        ],
        # B1, B2, B3 – Financial Health & Awareness
        "B": [col for col in columns if col.startswith(("B1", "B2", "B3"))],
        # C1 – Livelihood
        "C": [col for col in columns if col.startswith(("C1", "C2", "C3", "C4"))],
        # D1 – Pension
        "D1": [col for col in columns if col.startswith("D1", "D5", "D6")],
        # D – Insurance (Insurance)
        "D": [
            col for col in columns if col.startswith("D") and not col.startswith("D1")
        ],
        # E, E1, E2, E3 – Credit (the biggest section)
        "E": [col for col in columns if col.startswith("E1", "E2", "E3", "E4", "E5")],
        # F, F1, F2 – Savings & Investment
        "F": [col for col in columns if col.startswith("F1", "F2", "F3")],
        # G + H – Transactions & Banking
        "GH": [col for col in columns if col.startswith(("G", "H"))],
        # I – Credit-only MFI
        "I": [col for col in columns if col.startswith("I")],
        # J – SACCO
        "J": [col for col in columns if col.startswith("J")],
        # K1 + M – Mobile Money & Mobile Banking
        "KM": [col for col in columns if col.startswith(("K", "M"))],
        # L – Climate Financing
        "L": [col for col in columns if col.startswith("L")],
        # N – Chama/Group
        "N": [col for col in columns if col.startswith("N")],
        # O, P, Q – Assistance, Business, Agriculture
        "OPQ": [col for col in columns if col.startswith(("O", "P", "Q"))],
        # R1, R2, R3 – Resilience & Goals
        "R": [col for col in columns if col.startswith("R")],
        # S + T – Technology & Amenities
        "ST": [col for col in columns if col.startswith(("S", "T"))],
        # U – Demographics & Housing
        "U": [col for col in columns if col.startswith("U")],
    }


# TODO: get all columns with with a letter and number immediately after
