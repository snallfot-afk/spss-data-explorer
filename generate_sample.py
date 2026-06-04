"""Generate a sample .sav file for testing the SPSS Data Explorer."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyreadstat


def main(out_path: str = "sample.sav", n: int = 500, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)

    df = pd.DataFrame({
        "id": np.arange(1, n + 1),
        "age": rng.integers(18, 80, size=n),
        "gender": rng.choice([1, 2], size=n, p=[0.49, 0.51]),
        "education": rng.choice([1, 2, 3, 4, 5], size=n, p=[0.1, 0.25, 0.3, 0.25, 0.1]),
        "region": rng.choice([1, 2, 3, 4], size=n),
        "income": np.round(rng.normal(55000, 18000, size=n).clip(10000, None), 2),
        "satisfaction": rng.choice([1, 2, 3, 4, 5], size=n, p=[0.05, 0.15, 0.3, 0.35, 0.15]),
        "employed": rng.choice([0, 1], size=n, p=[0.2, 0.8]),
    })

    column_labels = {
        "id": "Respondent ID",
        "age": "Age in years",
        "gender": "Gender",
        "education": "Highest education completed",
        "region": "Region of residence",
        "income": "Annual income (USD)",
        "satisfaction": "Overall life satisfaction",
        "employed": "Currently employed",
    }

    variable_value_labels = {
        "gender": {1: "Male", 2: "Female"},
        "education": {
            1: "Less than high school",
            2: "High school",
            3: "Some college",
            4: "Bachelor's degree",
            5: "Graduate degree",
        },
        "region": {1: "North", 2: "South", 3: "East", 4: "West"},
        "satisfaction": {
            1: "Very dissatisfied",
            2: "Dissatisfied",
            3: "Neutral",
            4: "Satisfied",
            5: "Very satisfied",
        },
        "employed": {0: "No", 1: "Yes"},
    }

    pyreadstat.write_sav(
        df,
        out_path,
        column_labels=column_labels,
        variable_value_labels=variable_value_labels,
    )
    print(f"Wrote {out_path}: {n} rows, {len(df.columns)} columns")


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "sample.sav"
    main(out)
