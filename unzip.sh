#!/bin/bash

pushd grading/agents
unzip ../../students.zip
for i in */; do
    pushd "$i";
    z=*.zip;
    unzip -j $z;
    rm $z;
    popd;
done

rename 's/Group (\d+).*/$1/s' *

# fix some agents
mv 7/Agent_4.0.py 7/agent.py
popd
