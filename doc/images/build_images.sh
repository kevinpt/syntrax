#!/bin/sh

OPTS=-t

#syntrax -i syntax_menu.spec -o syntax_menu.svg $OPTS

for f in *.spec; do
  dest=${f%.*}.svg
  syntrax -i $f -o $dest $OPTS
  #echo $f ${f%.*}.svg
done

