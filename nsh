#!/usr/bin/env python3

import sys
import os
import nsh

if len(sys.argv) > 1:
    module = sys.argv[1]
else:
    connectors = nsh.Nsh.list_connectors()
    if len(connectors) > 0:
        if len(connectors) > 1:
            print('more than 1 protocol connector available:', file=sys.stderr)
            print('\n'.join('%s%s' % (cnctr, ' (default)' if idx == 0 else '')
                            for idx, cnctr in enumerate(connectors)),
                  file=sys.stderr)
        module = connectors[0]
    else:
        raise Exception('no protocol connectors available')

nsh.Nsh(module).cmdloop()
