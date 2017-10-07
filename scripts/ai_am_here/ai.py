#!/usr/bin/env python2.7

import argparse
import subprocess
import os

parser = argparse.ArgumentParser()
parser.add_argument("--output-receiver-host", default="localhost")
parser.add_argument("--pn-address", nargs="+")
args = parser.parse_args()

command = "python2.7 applications/learn_recall_improvise.py --output-receiver-host=%s --with-ui --model=autoencoder --pn-convert-to-z-up --learning-rate=0.0012 --max-angular-step=0.15 --auto-friction --novelty=0.2 --extension=0.5 --velocity=0.5 --factor=1 --preset=alien_egg" % args.output_receiver_host

if args.pn_address:
    command += " --pn-address %s" % " ".join(args.pn_address)

working_dir = "%s/../../movement_ai" % os.path.dirname(__file__)
print "Running %s in %s" % (command, working_dir)
subprocess.call(command, shell=True, cwd=working_dir)
