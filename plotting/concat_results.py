import pandas as pd
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

    for t in df_mem["Test"]:
        df_prim[df_prim["Test"] == t]["DPU"] = df_mem[df_mem["Test"] == t]["DPU"]
        df_prim[df_prim["Test"] == t]["M_C2D"] = df_mem[df_mem["Test"] == t]["M_C2D"]
        df_prim[df_prim["Test"] == t]["M_D2C"] = df_mem[df_mem["Test"] == t]["M_D2C"]
    
    df_prim.to_csv("/dev/stdout", index = False)