from dataclasses import dataclass
import pandas as pd
import numpy as np
import sys

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: concat_results.py <memclave csv> <prim csv>")
        sys.exit(1)

    df_mem = pd.read_csv(sys.argv[1])
    df_prim = pd.read_csv(sys.argv[2])

    if set(df_mem["Test"].to_numpy()) != set(df_prim["Test"].to_numpy()):
        print("Tests in the csv files do not match - Cannot join.")
        sys.exit(1)

    res = []

    for _, row in df_prim.iterrows():
        cur = {}

        cur["Test"] = row["Test"]
        cur["CPU"] = row["CPU"]
        cur["UPMEM"] = row["UPMEM"]
        cur["U_C2D"] = row["U_C2D"]
        cur["U_D2C"] = row["U_D2C"]

        res.append(cur)
    
    for _, row in df_mem.iterrows():
        cur = [cur for cur in res if cur["Test"] == row["Test"]][0]

        cur["DPU"] = row["DPU"]
        cur["M_C2D"] = row["M_C2D"]
        cur["M_D2C"] = row["M_D2C"]

    df = pd.DataFrame(data=res)
    df.to_csv("/dev/stdout", index=False)