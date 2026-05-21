#!/bin/bash

unzip upload.zip
rm upload.zip
for i in *; do
    pushd "$i";
    z=*.zip;
    unzip -j $z;
    rm $z;
    popd;
done

rename 's/Group (\d+).*/$1/s' *

# fix some agents
mv 7/Agent_4.0.py 7/agent.py
