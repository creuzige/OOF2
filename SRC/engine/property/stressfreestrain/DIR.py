# -*- python -*-
# $RCSfile: DIR.py,v $
# $Revision: 1.4 $
# $Author: langer $
# $Date: 2014/09/27 21:41:25 $

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

dirname = 'stressfreestrain'
if not DIM_3:
    clib = 'oof2engine'
else:
    clib = 'oof3dengine'
cfiles = ['stressfreestrain.C']
hfiles = ['stressfreestrain.h']
swigpyfiles = ['stressfreestrain.spy']
swigfiles = ['stressfreestrain.swg']
pyfiles = ['pystressfreestrain.py']
