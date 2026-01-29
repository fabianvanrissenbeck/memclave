#!/bin/bash

if [ "$#" != "2" ];
then
    echo "Usage: ./plot_all.sh <memclave output> <upmem output>"
    exit 1
fi

TIME=$(date +%s)

MEMCLAVE_OUTPUT="memclave-out-$TIME"
UPMEM_OUTPUT="upmem-out-$TIME"
OUTPUT="plot-out-$TIME"

mkdir -p $MEMCLAVE_OUTPUT
mkdir -p $UPMEM_OUTPUT
mkdir -p $OUTPUT

tar xf $1 -C $MEMCLAVE_OUTPUT
tar xf $2 -C $UPMEM_OUTPUT

if [ ! -d .venv ];
then
    echo "There is no python venv yet for plotting. Creating one."
    python3 -m venv .venv
    source ./.venv/bin/activate
    pip install -r requirements.txt
else
    source ./.venv/bin/activate
fi

if [ -f $MEMCLAVE_OUTPUT/output/prim_results.csv ] && [ -f $UPMEM_OUTPUT/output/prim_results.csv ];
then
    python3 concat_results.py $MEMCLAVE_OUTPUT/output/prim_results.csv $UPMEM_OUTPUT/output/prim_results.csv > $OUTPUT/prim.csv
    python3 plot_speedup.py --csv $OUTPUT/prim.csv
else
    echo "Prim results are missing in the output. Skipping plot creation."
fi

if [ -f $MEMCLAVE_OUTPUT/output/mlp_results.csv ] && [ -f $UPMEM_OUTPUT/output/mlp_results.csv ];
then
    sed -i '/Memclave/d' $UPMEM_OUTPUT/output/mlp_results.csv
    sed --quiet -i '/Memclave/p' $MEMCLAVE_OUTPUT/output/mlp_results.csv
    cat $UPMEM_OUTPUT/output/mlp_results.csv $MEMCLAVE_OUTPUT/output/mlp_results.csv > $OUTPUT/mlp_results.csv
    python3 plot_mlp.py --csv $OUTPUT/mlp_results.csv
else
    echo "MLP results are missing in the output. Skipping plot creation."
fi

if [ -f $MEMCLAVE_OUTPUT/output/bfs_results.csv ] && [ -f $UPMEM_OUTPUT/output/bfs_results.csv ];
then
    sed -i '/Memclave/d' $UPMEM_OUTPUT/output/bfs_results.csv
    sed --quiet -i '/Memclave/p' $MEMCLAVE_OUTPUT/output/bfs_results.csv
    cat $UPMEM_OUTPUT/output/bfs_results.csv $MEMCLAVE_OUTPUT/output/bfs_results.csv > $OUTPUT/bfs_results.csv
    python3 plot_bfs.py --csv $OUTPUT/bfs_results.csv
else
    echo "BFS results are missing in the output. Skipping plot creation."
fi

if [ -f $MEMCLAVE_OUTPUT/output/mram.csv ] && [ -f $UPMEM_OUTPUT/output/mram.csv ];
then
    echo "=== MRAM Throughput table ==="
    python3 mram-table.py $MEMCLAVE_OUTPUT/output/mram.csv $UPMEM_OUTPUT/output/mram.csv
    echo ""
else
    echo "MRAM results are missing in the output. Skipping table creation."
fi

if [ -f $MEMCLAVE_OUTPUT/output/crypto.csv ] && [ -f $MEMCLAVE_OUTPUT/output/sk.csv ];
then
    sed -i '/Key Exchange Done/d' $MEMCLAVE_OUTPUT/output/crypto.csv
    sed -i '/Benchmark Finished./d' $MEMCLAVE_OUTPUT/output/crypto.csv
    sed '/INFO/d' $MEMCLAVE_OUTPUT/output/sk.csv > $OUTPUT/subk.csv
    sed -i '/DPU,auth only/d' $OUTPUT/subk.csv
    echo "=== Microbenchmark Table ==="
    python3 microbench-table.py $MEMCLAVE_OUTPUT/output/crypto.csv $OUTPUT/subk.csv
    grep -e 'DPU Ready line' $MEMCLAVE_OUTPUT/output/sk.csv | head -1
    grep -e 'Key Exchange' $MEMCLAVE_OUTPUT/output/sk.csv | head -1
else
    echo "Results for microbenchmark table missing. Skipping table creation."
fi

rm -rf $MEMCLAVE_OUTPUT
rm -rf $UPMEM_OUTPUT
rm -rf $OUTPUT
