#!/usr/bin/env python

import time
import sys

start_time = time.time()
while True:
    t = time.time() - start_time
    print "    %s\r" % time.strftime("%M:%S", time.gmtime(t)),
    sys.stdout.flush()
    time.sleep(1)
