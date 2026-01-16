import pandas as pd
import sys

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: concat_results.py <memclave csv> <prim csv>")
        sys.exit(1)

    df_mem = pd.read_csv(sys.argv[1])
    df_prim = pd.read_csv(sys.argv[2])

    df_mem.sort_values("Test")
    df_prim.sort_values("Test")

    if set(df_mem["Test"].to_numpy()) != set(df_prim["Test"].to_numpy()):
        print("Tests in the csv files do not match - Cannot join.")
        sys.exit(1)
    
    df = pd.DataFrame()

    df["Test"] = df_mem["Test"]
    df["CPU"] = df_prim["CPU"]
    df["DPU"] = df_mem["DPU"]
    df["M_C2D"] = df_mem["M_C2D"]
    df["M_D2C"] = df_mem["M_D2C"]
    df["UPMEM"] = df_prim["UPMEM"]
    df["U_C2D"] = df_prim["U_C2D"]
    df["U_D2C"] = df_prim["U_D2C"]

    print(df)