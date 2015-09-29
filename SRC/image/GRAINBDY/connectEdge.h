// -*- C++ -*-
// $RCSfile: connectEdge.h,v $
// $Revision: 1.5 $
// $Author: langer $
// $Date: 2014/09/27 21:41:29 $

/* This software was produced by NIST, an agency of the U.S. government,
 * and by statute is not subject to copyright in the United States.
 * Recipients of this software assume all responsibilities associated
 * with its operation, modification and maintenance. However, to
 * facilitate maintenance we ask that before distributing modifed
 * versions of this software, you first contact the authors at
 * oof_manager@nist.gov. 
 */

#include <oofconfig.h>

#ifndef CONNECTEDGE_H
#define CONNECTEDGE_H

class DoubleArray;
class BoolArray;

BoolArray connect(const DoubleArray&,double,double, int,int,int,bool);

#endif // CONNECTEDGE_H
