#!/bin/bash

# run gs_scraper.py with each faculty member name in faculty_info.txt

while IFS='' read -r line || [[ -n "$line" ]]; do
    IFS=',' read -ra field <<< "$line"
    for i in "${field[0]}"; do
        python3 test_script.py $i max 5
    done
done < "faculty_info.txt"

python3 test_script.py ws-dl.txt start 2002

python3 test_script.py cs_dept.txt
