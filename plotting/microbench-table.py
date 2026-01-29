import sys
import pandas as pd

def to_sec(cycles):
    return cycles / 350000000

def to_msec(cycles):
    return cycles / 350000

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: microbench-table.py <output crypto> <output subk>")
        sys.exit(1)

    columns=["DPU", "auth only", "unload", "auth", "dec", "scan"]
    crypto = pd.read_csv(sys.argv[1])
    subk = pd.read_csv(sys.argv[2], header=0, names=columns)

    size = crypto["size"].mean()
    time = to_sec(crypto["cycles"].mean())
    print(f"Sealed EM Transfer: {size / time / 1024 / 1024} MiB/s")

    # numbers reported by subkernel loading benchmark accumulate over time
    # fix this to get concrete cycle counts per measurement interval

    subk["scan"] -= subk["dec"]
    subk["dec"] -= subk["auth"]
    subk["auth"] -= subk["unload"]

    sk_auth = subk[subk["auth only"] == True]
    sk_norm = subk[subk["auth only"] == False]

    print("SK load (Auth; Enc; Scan) (ms) & & {} ({}, {}, {}) & {} ({}, {}, {})".format(
        to_msec(sk_auth["auth"].mean() + sk_auth["dec"].mean() + sk_auth["scan"].mean()),
        to_msec(sk_auth["auth"].mean()),
        to_msec(sk_auth["dec"].mean()),
        to_msec(sk_auth["scan"].mean()),
        to_msec(sk_norm["auth"].mean() + sk_norm["dec"].mean() + sk_norm["scan"].mean()),
        to_msec(sk_norm["auth"].mean()),
        to_msec(sk_norm["dec"].mean()),
        to_msec(sk_norm["scan"].mean())
    ))

    print("SK Unload (ms) & & {} & {}".format(to_msec(sk_auth["unload"].mean()), to_msec(sk_norm["unload"].mean())))

    
