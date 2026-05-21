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
