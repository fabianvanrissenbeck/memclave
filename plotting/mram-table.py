import pandas as pd
import sys

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: mram-table.py <mram memclave> <mram upmem>")
        sys.exit(1)

    data_baseline = pd.read_csv(sys.argv[2])
    data_memclave = pd.read_csv(sys.argv[1])

    data_baseline["arch"] = "upmem"
    data_memclave["arch"] = "memclave"

    data = pd.concat([data_baseline, data_memclave])

    data = data[data["size"] == 16 << 20]
    data_tf = data[data["type"] == "transfer"]
    data_bc = data[data["type"] == "broadcast"]
    data_gt = data[data["type"] == "gather"]
    data_row = [data_bc, data_tf, data_gt]
    rows = ["Broadcast", "Transfer", "Gather  "]

    print("\t\t\tUPMEM    MC_8    MC_12")

    for row, name in zip(data_row, rows):
        upmem = row[row["arch"] == "upmem"]
        upmem_8 = upmem[upmem["threads"] == 8]
        memclave = row[row["arch"] == "memclave"]
        memclave_12 = memclave[memclave["threads"] == 12]
        memclave_8 = memclave[memclave["threads"] == 8]

        field = "transfer rate (MB/s)"

        res = [
            upmem_8[field].mean(),
            memclave_8[field].mean(),
            memclave_12[field].mean()
        ]

        print("{}\t & {:>8.2f} & {:>8.2f} & {:>8.2f} \\\\".format(
            name,
            res[0],
            res[1],
            res[2],
        ))