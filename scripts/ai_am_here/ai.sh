#!/bin/sh

if [ "$1" = "" ]; then
   echo "Specify PN IP address."
   exit
fi

cd movement_ai
python2.7 applications/ai_human_duet.py --output-receiver-host=localhost --enable-improvise --with-ui --model=autoencoder --delay-shift=0 --mirror-duration=5 --improvise-duration=5 --recall-duration=5 --pn-convert-to-z-up --pn-host=$1
