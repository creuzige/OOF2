# -*- python -*- 


# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modifed
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

dirname = 'IO'
if not DIM_3:
    clib = 'oof2engine'
else:
    clib = 'oof3dengine'
if not NO_GUI:
    subdirs = ['GUI']

cfiles = ['contour.C', 'propertyoutput.C']

swigfiles = ['contour.swg', 'propertyoutput.swg']

pyfiles = [ 'analyze.py', 'analyzemenu.py', 'anisocijkl.py',
            'boundaryconditionmenu.py', 'boundarymenu.py',
            'centerfilldisplay.py', 'contourdisplay.py', 'displaymethods.py',
            'elementselectdisplay.py', 'interfacemenu.py',
            'interfaceparameters.py', 'isocijkl.py', 'materialmenu.py',
            'materialparameter.py', 'meshIO.py', 'meshbdymenu.py',
            'meshcsdisplay.py', 'meshcsparams.py', 'meshcstoolbox.py',
            'meshinfo.py', 'meshinfodisplay.py', 'meshmenu.py',
            'meshparameters.py', 'microstructuredisplay.py', 'movenode.py',
            'movenodedisplay.py', 'nodeselectdisplay.py',
            'orientationmatrix.py', 'output.py', 'outputClones.py',
            'outputDefs.py', 'outputdestination.py', 'pbcparams.py',
            'pinnodes.py', 'pinnodesdisplay.py', 'pinnodesmenu.py',
            'propertymenu.py', 'propertyoutputreg.py', 'scheduledoutput.py',
            'scheduledoutputmenu.py', 'segmentselectdisplay.py',
            'skeletonIO.py', 'skeletonbdydisplay.py', 'skeletongroupmenu.py',
            'skeletongroupparams.py', 'skeletoninfo.py',
            'skeletoninfodisplay.py', 'skeletonmenu.py',
            'skeletonselectiontoolbox.py', 'skeletonselectmenu.py',
            'subproblemmenu.py', 'xmloutputs.py', ]

swigpyfiles = ['contour.spy', 'propertyoutput.spy']

hfiles = ['contour.h', 'propertyoutput.h']

if DIM_3:
    cfiles.remove('contour.C')
    swigfiles.remove('contour.swg')
    swigpyfiles.remove('contour.spy')
    hfiles.remove('contour.h')


if HAVE_MPI:
    pyfiles.extend(['boundaryconditionIPC.py', 'meshIPC.py',
                    'propertymenuIPC.py',
                    'skeletonIPC.py', 'materialmenuIPC.py', 'solvermenuIPC.py',
                    'subproblemIPC.py'])
